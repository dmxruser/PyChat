import os
import time
import threading
import base64
import socket
import json
import requests

# Pip-installed libraries
from flask import Flask, request, jsonify
from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf, IPVersion

# Local imports
from .discovery import get_local_ip
import logging

# module logger
logger = logging.getLogger('pychat')


# --- Shared Constants ---
SERVICE_TYPE = "_pychat._tcp.local."
SERVER_PORT = 5000

# --- Networking Logic ---
class NetworkManager:
    def __init__(self, name, chat_code, on_message=None):
        self.name = name
        self.chat_code = chat_code
        self.on_message = on_message
        self.zeroconf = Zeroconf()
        self.service_info = None
        self.flask_thread = None
        self.chat_filename = os.path.join("chats", f"{self.chat_code}.txt")

    def start(self):
        # Set up debugging but disable regular Flask logs
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        app = Flask(__name__)
        app.logger.disabled = True

        # Make sure we have an absolute path to the chat file
        self.chat_filename = os.path.abspath(self.chat_filename)
        logger.debug(f"Starting server with chat file: {self.chat_filename}")

        # Create the file if it doesn't exist
        if not os.path.exists(self.chat_filename):
            open(self.chat_filename, 'wb').close()
            logger.debug(f"Created new chat file: {self.chat_filename}")

        @app.route('/messages', methods=['GET'])
        def get_messages():
            since_time = float(request.args.get('since', '0'))
            logger.debug(f"Fetching messages since timestamp {since_time}")

            if not os.path.exists(self.chat_filename):
                logger.debug(f"Chat file {self.chat_filename} does not exist")
                return jsonify([])

            messages = []
            try:
                # Check if the file has been modified since the last poll
                file_mod_time = os.path.getmtime(self.chat_filename)
                if file_mod_time < since_time:
                    return jsonify([])

                with open(self.chat_filename, "rb") as f:
                    data = f.read()

                if data:
                    # Split into messages
                    chunks = data.split(b'\0')
                    logger.debug(f"Found {len(chunks)} total chunks in file")

                    # Include all non-empty chunks for now
                    for chunk in chunks:
                        if chunk:  # Skip empty chunks
                            messages.append(base64.b64encode(chunk).decode('utf-8'))

                    logger.debug(f"Returning {len(messages)} messages")
                else:
                    logger.debug("Chat file is empty")

            except Exception as e:
                logger.error(f"Error reading messages: {e}")

            return jsonify(messages)

        # Store connected clients for broadcasting
        connected_clients = set()

        def broadcast_message(encrypted_message):
            """Broadcast a message to all connected clients"""
            if not connected_clients:
                logger.debug("No connected clients to broadcast to")
                return

            message_b64 = base64.b64encode(encrypted_message).decode('utf-8')
            logger.debug(f"Broadcasting message to {len(connected_clients)} clients")

            def send_to_client(client_url):
                try:
                    logger.debug(f"Sending to client at {client_url}")
                    # Use the client's /client_message endpoint
                    response = requests.post(
                        f"{client_url}/client_message",
                        json={'message': message_b64},
                        timeout=2
                    )
                    if response.status_code != 200:
                        logger.error(f"Error from {client_url}: {response.status_code} - {response.text}")
                        return False
                    logger.debug(f"Successfully sent to {client_url}")
                    return True
                except Exception as e:
                    logger.error(f"Error broadcasting to {client_url}: {str(e)}")
                    # Remove disconnected client
                    connected_clients.discard(client_url)
                    logger.info(f"Removed disconnected client: {client_url}")
                    return False

            # Send to all clients in parallel
            threads = []
            results = {}

            clients = list(connected_clients)  # Create a copy to avoid modification during iteration
            logger.debug(f"Client URLs: {clients}")

            for client_url in clients:
                t = threading.Thread(
                    target=lambda url=client_url: results.update({url: send_to_client(url)}),
                    daemon=True
                )
                t.start()
                threads.append(t)

            # Wait for all sends to complete with a timeout
            for t in threads:
                t.join(timeout=5)

        @app.route('/message', methods=['POST'])
        def handle_message():
            """Handle incoming messages from clients and other servers"""
            encrypted_message_b64 = request.json.get('message')
            if not encrypted_message_b64:
                logger.debug("Received empty message")
                return jsonify({"error": "empty message"}), 400

            try:
                encrypted_message = base64.b64decode(encrypted_message_b64)
                logger.debug(f"Received message from {request.remote_addr}, size: {len(encrypted_message)} bytes")

                # Store the message in the chat file
                with open(self.chat_filename, "ab") as f:
                    # Write message followed by null byte as separator
                    f.write(encrypted_message + b'\0')
                    logger.debug(f"Wrote message to {self.chat_filename}")

                # Broadcast to all connected clients
                broadcast_message(encrypted_message)

                # Call the callback for the local server to process the message
                if self.on_message:
                    try:
                        self.on_message(encrypted_message)
                        logger.debug("Message callback executed successfully")
                    except Exception as e:
                        logger.error(f"Error in message callback: {e}")

                return jsonify({"status": "ok"})

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                return jsonify({"error": str(e)}), 500

        @app.route('/connect', methods=['POST'])
        def connect_client():
            """Register a client for message broadcasting"""
            client_url = request.json.get('url')
            if client_url:
                # Remove http:// or https:// if present
                client_url = client_url.replace('http://', '').replace('https://', '')
                # Add http:// if no scheme is present
                if not client_url.startswith(('http://', 'https://')):
                    client_url = f"http://{client_url}"
                connected_clients.add(client_url)
                logger.debug(f"Client connected: {client_url}")
                logger.debug(f"Current connected clients: {connected_clients}")
            return jsonify({"status": "ok"})

        # Register the service
        service_name = f"{self.name}.{SERVICE_TYPE}"
        self.service_info = ServiceInfo(
            SERVICE_TYPE,
            service_name,
            addresses=[socket.inet_aton(get_local_ip())],
            port=SERVER_PORT,
            properties={b'chat_code': os.path.basename(self.chat_filename).split('.')[0].encode('utf-8')}
        )
        self.zeroconf.register_service(self.service_info)
        logger.debug(f"Registered service: {service_name}")

        # Run Flask app in a separate thread
        def run_flask():
            # lower werkzeug log level to avoid noisy HTTP logs
            logging.getLogger('werkzeug').setLevel(logging.WARNING)
            app.run(host='0.0.0.0', port=SERVER_PORT)

        self.flask_thread = threading.Thread(target=run_flask)
        self.flask_thread.daemon = True
        self.flask_thread.start()

    def stop(self):
        if self.service_info:
            self.zeroconf.unregister_service(self.service_info)
        self.zeroconf.close()
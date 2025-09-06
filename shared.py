# Made with the assistance of AI

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
from cleanerfile import get_local_ip
import logging

# module logger
logger = logging.getLogger('pychat')


# --- Shared Constants ---
SERVICE_TYPE = "_pychat._tcp.local."
SERVER_PORT = 5000

# --- Networking Logic ---

def send_file(file_path, server_url):
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f.read())}
            response = requests.post(f"{server_url}/receive_file", files=files)
            if response.status_code == 200:
                print("File sent successfully.")
            else:
                print(f"Failed to send file. Server returned status code {response.status_code}")
    except Exception as e:
        print(f"Error sending file: {e}")

def run_server(zeroconf, name, chat_filename, own_public_key=None, on_message_callback=None):
    app = Flask(__name__)

    # own_public_key: this server's public key bytes (optional)
    server_own_public_key = own_public_key
    # peer_public_key will be set when a client posts its public key
    peer_public_key_bytes = None

    @app.route('/messages', methods=['GET'])
    def get_messages():
        since_index = int(request.args.get('since', 0))
        if os.path.exists(chat_filename):
            with open(chat_filename, "rb") as f:
                lines = f.readlines()
            # Return messages as a list of base64 encoded strings
            return jsonify([base64.b64encode(line.strip()).decode('utf-8') for line in lines[since_index:]])
        return jsonify([])

    @app.route('/message', methods=['POST'])
    def post_message():
        encrypted_message_b64 = request.json.get('message')
        encrypted_message = base64.b64decode(encrypted_message_b64)
        with open(chat_filename, "ab") as f:
            f.write(encrypted_message + b'\n')
        # Invoke optional callback (in-flask thread) so the hosting process can react immediately
        if on_message_callback:
            try:
                on_message_callback(encrypted_message)
            except Exception:
                logger.exception('on_message_callback failed')
        return jsonify({"status": "ok"})

    @app.route('/receive_file', methods=['POST'])
    def receive_file():
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        if file:
            if not os.path.exists("sharedkeys"):
                os.makedirs("sharedkeys")
            file.save(os.path.join("sharedkeys", file.filename))
            return jsonify({"status": "ok"})

    @app.route('/public_key', methods=['GET', 'POST'])
    def public_key():
        """GET returns this server's public key; POST accepts peer public key."""
        nonlocal server_own_public_key, peer_public_key_bytes
        if request.method == 'POST':
            pk_b64 = request.json.get('public_key')
            if not pk_b64:
                return jsonify({'error': 'no public_key provided'}), 400
            pk = base64.b64decode(pk_b64)
            # save to sharedkeys folder
            if not os.path.exists('sharedkeys'):
                os.makedirs('sharedkeys')
            filename = f"sharedkeys/peer_{int(time.time())}.key"
            with open(filename, 'wb') as f:
                f.write(pk)
            peer_public_key_bytes = pk
            return jsonify({'status': 'ok', 'saved_as': filename})
        else:
            # return this server's own public key (if provided)
            if server_own_public_key:
                return jsonify({'public_key': base64.b64encode(server_own_public_key).decode('utf-8')})
            return jsonify({'public_key': None})

    @app.route('/peer_public_key', methods=['GET'])
    def get_peer_public_key():
        nonlocal peer_public_key_bytes
        if peer_public_key_bytes:
            return jsonify({'public_key': base64.b64encode(peer_public_key_bytes).decode('utf-8')})
        return jsonify({'public_key': None})

    # Register the service
    service_name = f"{name}.{SERVICE_TYPE}"
    info = ServiceInfo(
        SERVICE_TYPE,
        service_name,
        addresses=[socket.inet_aton(get_local_ip())],
        port=SERVER_PORT,
        properties={b'chat_code': os.path.basename(chat_filename).split('.')[0].encode('utf-8')}
    )
    zeroconf.register_service(info)
    logger.debug(f"Registered service: {service_name}")

    # Run Flask app in a separate thread
    def run_flask():
        # lower werkzeug log level to avoid noisy HTTP logs
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        app.run(host='0.0.0.0', port=SERVER_PORT)

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    return info

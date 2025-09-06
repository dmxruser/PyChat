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

def run_server(zeroconf, name, chat_filename, server_public_key=None):
    app = Flask(__name__)

    # store server's own public key bytes (optional)
    server_public_key_bytes = server_public_key

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
        nonlocal server_public_key_bytes
        if request.method == 'POST':
            pk_b64 = request.json.get('public_key')
            if not pk_b64:
                return jsonify({'error': 'no public_key provided'}), 400
            pk = base64.b64decode(pk_b64)
            # save to sharedkeys folder
            if not os.path.exists('sharedkeys'):
                os.makedirs('sharedkeys')
            filename = f"sharedkeys/partner_{int(time.time())}.key"
            with open(filename, 'wb') as f:
                f.write(pk)
            server_public_key_bytes = pk
            return jsonify({'status': 'ok', 'saved_as': filename})
        else:
            if server_public_key_bytes:
                return jsonify({'public_key': base64.b64encode(server_public_key_bytes).decode('utf-8')})
            return jsonify({'public_key': None})

    # Register the service
    service_name = f"{name}.{SERVICE_TYPE}"
    info = ServiceInfo(
        SERVICE_TYPE,
        service_name,
        addresses=[socket.inet_aton(get_local_ip())],
        port=SERVER_PORT,
        properties={'chat_code': os.path.basename(chat_filename).split('.')[0]}
    )
    zeroconf.register_service(info)
    print(f"Registered service: {service_name}")

    # Run Flask app in a separate thread
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=SERVER_PORT))
    flask_thread.daemon = True
    flask_thread.start()

    return info

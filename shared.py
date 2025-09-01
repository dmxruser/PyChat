# Made with the assistance of AI

import os
import time
import threading
import base64
import socket
import json

# Pip-installed libraries
from flask import Flask, request, jsonify
from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf, IPVersion
import requests

# --- Shared Constants ---
SERVICE_TYPE = "_pychat._tcp.local."
SERVER_PORT = 5000

# --- Networking Logic ---

class ServiceListener:
    def __init__(self):
        self.found_services = []

    def remove_service(self, zeroconf, type, name):
        print(f"Service {name} removed")
        self.found_services = [s for s in self.found_services if s.name != name]

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            self.found_services.append(info)
            print(f"Service {name} added, service info: {info}")

    def get_address(self):
        if self.found_services:
            info = self.found_services[0]
            addresses = info.addresses_by_version(IPVersion.V4)
            if addresses:
                return f"http://{socket.inet_ntoa(addresses[0])}:{info.port}"
        return None

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def run_server(zeroconf, name, chat_filename):
    app = Flask(__name__)

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

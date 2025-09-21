import os
import socket
import logging
from zeroconf import IPVersion

# Import config
from . import config

# Use a module logger so the user can control verbosity via logging configuration
logger = logging.getLogger('pychat')

def load_peer_public_key(my_public_key):
    """Loads the peer's public key from the sharedkeys directory."""
    os.makedirs(config.SHARED_KEYS_DIR, exist_ok=True)
    for filename in os.listdir(config.SHARED_KEYS_DIR):
        if filename.startswith("public_"):
            try:
                peer_pk_path = os.path.join(config.SHARED_KEYS_DIR, filename)
                with open(peer_pk_path, "rb") as f:
                    peer_pk = f.read()
                if peer_pk != my_public_key:
                    logger.debug(f"Found peer public key: {filename}")
                    return peer_pk
            except Exception as e:
                logger.error(f"Error loading peer public key {filename}: {e}")
    return None

class ServiceListener:
    def __init__(self):
        self.found_services = {}

    def remove_service(self, zeroconf, type, name):
        logger.debug(f"Service {name} removed")
        if name in self.found_services:
            del self.found_services[name]

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            chat_code = info.properties.get(b'chat_code', b'').decode('utf-8')
            self.found_services[chat_code] = info
            logger.debug(f"Service {name} added, service info: {info}")

    def update_service(self, zeroconf, type, name):
        """Handle service updates - required by zeroconf."""
        info = zeroconf.get_service_info(type, name)
        if info:
            chat_code = info.properties.get(b'chat_code', b'').decode('utf-8')
            self.found_services[chat_code] = info
            logger.debug(f"Service {name} updated, new info: {info}")

    def get_address(self, chat_code):
        if chat_code in self.found_services:
            info = self.found_services[chat_code]
            addresses = info.addresses_by_version(IPVersion.V4Only)
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
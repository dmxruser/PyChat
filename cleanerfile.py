# Made with the assistance of AI

import os
import socket
import shutil
from zeroconf import IPVersion
def movePubkey():
    for file in os.listdir("./sharedkeys"):
        if file.startswith("public_."):
            print(file)
class ServiceListener:
    def __init__(self):
        self.found_services = {}

    def remove_service(self, zeroconf, type, name):
        print(f"Service {name} removed")
        if name in self.found_services:
            del self.found_services[name]

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            chat_code = info.properties.get(b'chat_code', b'').decode('utf-8')
            self.found_services[chat_code] = info
            print(f"Service {name} added, service info: {info}")

    def get_address(self, chat_code):
        if chat_code in self.found_services:
            info = self.found_services[chat_code]
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
# config.py

# Made with the assistance of AI

import os

# --- Directory Configuration ---
# Use an environment variable to set a base directory, falling back to the script's location.
APP_BASE_DIR = os.environ.get("PYCHAT_BASE_DIR", os.path.dirname(os.path.abspath(__file__)))

KEYS_DIR = os.path.join(APP_BASE_DIR, "keys")
SHARED_KEYS_DIR = os.path.join(APP_BASE_DIR, "sharedkeys")
CHATS_DIR = os.path.join(APP_BASE_DIR, "chats")

def initialize_directories():
    """Creates the necessary directories if they don't exist."""
    os.makedirs(KEYS_DIR, exist_ok=True)
    os.makedirs(SHARED_KEYS_DIR, exist_ok=True)
    os.makedirs(CHATS_DIR, exist_ok=True)

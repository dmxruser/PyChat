# main.py

# Made with the assistance of AI

import os
import time
import threading
import base64
import random
from quantcrypt.kem import Kyber1024
from quantcrypt.symmetric import Krypton
from zeroconf import Zeroconf, ServiceBrowser

# Local imports
from shared import (
    SERVICE_TYPE,
    ServiceListener,
    run_server,
    requests
)

# --- Key Management Functions ---
# (These remain here as they involve direct user interaction via print)

def generate_and_save_keys():
    """Generates a private/public key pair with random filenames and saves them."""
    print("\nGenerating new key pair...")
    public_key, private_key = Kyber1024.generate_keypair()

    code = str(random.randint(100000, 999999))
    private_key_filename = f"private_{code}.key"
    public_key_filename = f"public_{code}.key"

    with open(private_key_filename, "wb") as f:
        f.write(private_key)
    
    with open(public_key_filename, "wb") as f:
        f.write(public_key)
    
    print("\n--- New Keys Generated ---")
    print(f"Your new private key is saved as: {private_key_filename} (KEEP THIS SECRET)")
    print(f"Your new public key is saved as: {public_key_filename} (share this one with your partner)")
    print("--------------------------\n")

def load_private_key(key_path):
    """Loads the user's private key from a given path."""
    try:
        with open(key_path, "rb") as f:
            private_key = f.read()
        return private_key
    except FileNotFoundError:
        print(f"Error: Private key file not found at '{key_path}'.")
        return None
    except Exception as e:
        print(f"Error loading private key: {e}")
        return None

def load_public_key(key_path):
    """Loads a public key from a given file path."""
    try:
        with open(key_path, "rb") as f:
            public_key = f.read()
        return public_key
    except FileNotFoundError:
        print(f"Error: Public key file not found at '{key_path}'.")
        return None
    except Exception as e:
        print(f"Error loading public key: {e}")
        return None

# --- Core Chat Functions ---

def encrypt_message(message, public_key):
    """Encrypts a message and returns the combined encapsulated key and ciphertext."""
    shared_secret, encapsulated_key = Kyber1024.encapsulate_key(public_key)
    encrypted_payload = Krypton.encrypt(shared_secret, message.encode('utf-8'))
    return base64.b64encode(encapsulated_key) + b':' + base64.b64encode(encrypted_payload)

def decrypt_message(encrypted_data, private_key):
    """Decrypts an incoming message."""
    encapsulated_key_b64, encrypted_payload_b64 = encrypted_data.split(b':')
    encapsulated_key = base64.b64decode(encapsulated_key_b64)
    encrypted_payload = base64.b64decode(encrypted_payload_b64)
    shared_secret = Kyber1024.decapsulate_key(private_key, encapsulated_key)
    decrypted_payload = Krypton.decrypt(shared_secret, encrypted_payload)
    return decrypted_payload.decode('utf-8')

# --- Listener Functions ---

def client_message_listener(stop_event, server_url, private_key):
    """Runs in a background thread for the client, polling the server for new messages."""
    last_message_count = 0
    while not stop_event.is_set():
        try:
            response = requests.get(f"{server_url}/messages", params={'since': last_message_count}, timeout=5)
            if response.status_code == 200:
                new_messages_b64 = response.json()
                if new_messages_b64:
                    for encrypted_message_b64 in new_messages_b64:
                        try:
                            decrypted = decrypt_message(base64.b64decode(encrypted_message_b64), private_key)
                            print(f"\r{decrypted}\n> ", end="")
                        except Exception as e:
                            pass
                    last_message_count += len(new_messages_b64)
        except requests.exceptions.RequestException:
            time.sleep(2)
        time.sleep(1)

def server_message_listener(private_key, chat_filename, stop_event):
    """The original message listener, for the server to read its own file."""
    last_read_position = 0
    if os.path.exists(chat_filename):
        last_read_position = os.path.getsize(chat_filename)

    while not stop_event.is_set():
        try:
            if os.path.exists(chat_filename):
                current_size = os.path.getsize(chat_filename)
                if current_size > last_read_position:
                    with open(chat_filename, "rb") as chat_file:
                        chat_file.seek(last_read_position)
                        for line in chat_file:
                            try:
                                decrypted = decrypt_message(line.strip(), private_key)
                                print(f"\r{decrypted}\n> ", end="")
                            except Exception:
                                pass
                    last_read_position = current_size
        except FileNotFoundError:
            pass
        time.sleep(1)

# --- Main Application ---

def main():
    # --- Setup ---
    name = input("Enter your name: ")
    
    my_private_key = None
    while my_private_key is None:
        private_key_path = input("Enter path to your private key (or type .generate): ")
        if private_key_path.lower() == '.generate':
            generate_and_save_keys()
            continue
        my_private_key = load_private_key(private_key_path)
        if my_private_key is None:
            print("Please try again.")

    partner_public_key = None
    while partner_public_key is None:
        partner_key_path = input("Enter path to your partner's public key file: ")
        partner_public_key = load_public_key(partner_key_path)
        if partner_public_key is None:
            print("Please try again.")
    
    chat_code = input("Enter a unique Chat Code for this session: ")
    chat_filename = f"{chat_code}.txt"

    # --- Peer Discovery ---
    zeroconf = Zeroconf()
    listener = ServiceListener()
    browser = ServiceBrowser(zeroconf, SERVICE_TYPE, listener)
    
    print("\nLooking for your partner on the network...")
    time.sleep(5) # Wait 5 seconds for a service to be discovered

    server_url = listener.get_address()
    stop_event = threading.Event()

    try:
        if server_url:
            # --- Client Mode ---
            print(f"Partner found! Connecting to {server_url}...")
            
            listener_thread = threading.Thread(target=client_message_listener, args=(stop_event, server_url, my_private_key), daemon=True)
            listener_thread.start()

            print("\n--- E2EE Chat Started (Client Mode) ---")
            print("Type '.exit' to quit.")

            while True:
                message = input("> ")
                if message.lower() == '.exit':
                    break
                if message:
                    full_message = f"{name}: {message}"
                    encrypted_message = encrypt_message(full_message, partner_public_key)
                    try:
                        requests.post(f"{server_url}/message", json={'message': base64.b64encode(encrypted_message).decode('utf-8')})
                    except requests.exceptions.RequestException:
                        print("Error: Could not connect to partner. Exiting.")
                        break
        
        else:
            # --- Server Mode ---
            print("No partner found. Starting in server mode and waiting for them to connect...")
            server_info = run_server(zeroconf, name, chat_filename)
            
            listener_thread = threading.Thread(target=server_message_listener, args=(my_private_key, chat_filename, stop_event), daemon=True)
            listener_thread.start()

            print("\n--- E2EE Chat Started (Server Mode) ---")
            print("Type '.exit' to quit.")

            while True:
                message = input("> ")
                if message.lower() == '.exit':
                    break
                if message:
                    full_message = f"{name}: {message}"
                    encrypted_message = encrypt_message(full_message, partner_public_key)
                    with open(chat_filename, "ab") as encrypted_file:
                        encrypted_file.write(encrypted_message + b'\n')

    finally:
        print("\nExiting Pychat. Goodbye!")
        stop_event.set()
        zeroconf.close()

if __name__ == "__main__":
    main()
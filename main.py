# main.py

# Made with the assistance of AI

import os
import time
import threading
import base64
import random
import shutil
from quantcrypt.cipher import Krypton
from quantcrypt.kem import MLKEM_1024
from zeroconf import Zeroconf, ServiceBrowser
import requests
import hashlib

# Local imports
from shared import (
    SERVICE_TYPE,
    run_server,
    SERVER_PORT,
)
from cleanerfile import ServiceListener
import logging

# Use module logger
logger = logging.getLogger('pychat')


# --- Key Management Functions ---
# (These remain here as they involve direct user interaction via print)

kem = MLKEM_1024()
# hashes of encrypted payloads the local host wrote (so the file-watcher can ignore them)
sent_message_hashes = set()

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

# --- Core Chat Functions ---

def encrypt_message(message, public_key):
    """Encrypts a message and returns the combined encapsulated key and ciphertext."""
    encaps, shared = kem.encaps(public_key)
    # Krypton requires a 64-byte secret; expand the KEM shared secret using SHA3_512
    from Cryptodome.Hash import SHA3_512
    key64 = SHA3_512.new(shared).digest()
    # Krypton usage: create instance with 64-byte shared secret
    k = Krypton(key64)
    k.begin_encryption()
    ct = k.encrypt(message.encode('utf-8'))
    verif = k.finish_encryption()
    payload = encaps + verif + ct
    # return raw payload (server stores raw bytes; transport uses base64)
    return payload

def decrypt_message(encrypted_data, private_key):
    """Decrypts an incoming message.

    Accepts either a base64-encoded string/bytes (from the network)
    or raw payload bytes (from the local chat file).
    """
    try:
        # normalize to raw bytes
        if isinstance(encrypted_data, (bytes, bytearray)):
            raw = bytes(encrypted_data)
        else:
            # assume it's a base64 string
            raw = base64.b64decode(encrypted_data)

        # encapsulated key size from MLKEM params
        encaps_size = kem.param_sizes.ct_size
        verif_size = 160  # Krypton verification tag size

        # Require minimum message size (don't pad anymore, it breaks verification)
        if len(raw) < encaps_size + verif_size:
            raise ValueError(f"Message too short: {len(raw)} bytes")

        # Split the message into its components
        encaps = raw[:encaps_size]
        verif = raw[encaps_size:encaps_size + verif_size]
        ct = raw[encaps_size + verif_size:]

        # Perform KEM decapsulation to get shared secret
        shared = kem.decaps(private_key, encaps)
        
        # Derive symmetric key
        from Cryptodome.Hash import SHA3_512
        key64 = SHA3_512.new(shared).digest()

        # Initialize Krypton with verification tag
        k = Krypton(key64)
        k.begin_decryption(verif)

        # Decrypt the actual message
        pt = k.decrypt(ct)
        return pt.decode('utf-8')

    except Exception as e:
        # Log error details for debugging
        logger.debug(f"Decryption failed: {e}, message length: {len(raw) if 'raw' in locals() else 'unknown'}")
        raise  # Re-raise the original error

# --- Listener Functions ---

def display_message(text):
    # Prints an incoming message while preserving the input prompt
    try:
        print(f"\r{text}\n> ", end="")
    except Exception:
        print(text)


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
                        if not encrypted_message_b64:
                            continue
                        try:
                            # encrypted_message_b64 is a base64 string from the server; pass it directly
                            decrypted = decrypt_message(encrypted_message_b64, private_key)
                            display_message(decrypted)
                        except Exception as e:
                            # Don't silently fail
                            display_message(f"[System] Error decrypting a message: {e}")
                    last_message_count += len(new_messages_b64)
        except requests.exceptions.RequestException:
            time.sleep(2)
        time.sleep(1)

def server_message_listener(private_key, chat_filename, stop_event):
    """The original message listener, for the server to read its own file."""
    last_read_position = 0
    if os.path.exists(chat_filename):
        last_read_position = os.path.getsize(chat_filename)

    # Expected size for MLKEM-1024: encapsulated (1568) + verif (160) + message
    MIN_MESSAGE_SIZE = kem.param_sizes.ct_size + 160

    while not stop_event.is_set():
        try:
            if os.path.exists(chat_filename):
                current_size = os.path.getsize(chat_filename)
                if current_size > last_read_position:
                    with open(chat_filename, "rb") as chat_file:
                        chat_file.seek(last_read_position)
                        for line in chat_file:
                            try:
                                # Use removesuffix to avoid stripping meaningful bytes from the payload
                                clean_line = line.removesuffix(b'\n')
                                if not clean_line:
                                    continue

                                # Skip messages we wrote ourselves (recorded by hash)
                                h = hashlib.sha256(clean_line).hexdigest()
                                if h in sent_message_hashes:
                                    sent_message_hashes.discard(h)
                                    continue

                                # Verify message has minimum required length before attempting decryption
                                if len(clean_line) < MIN_MESSAGE_SIZE:
                                    continue  # Skip truncated/corrupted messages silently

                                decrypted = decrypt_message(clean_line, private_key)
                                display_message(decrypted)
                            except Exception as e:
                                display_message(f"[System] Error decrypting a message: {e}")
                    last_read_position = current_size
        except FileNotFoundError:
            pass
        time.sleep(1)


# --- Main Application ---

def main():
    name = input("Enter your name: ")
    chat_code = input("Enter a unique Chat Code for this session: ")
    chat_filename = f"{chat_code}.txt"

    # Generate my key pair
    my_public_key, my_private_key = kem.keygen()

    # --- Peer Discovery ---
    zeroconf = Zeroconf()
    listener = ServiceListener()
    browser = ServiceBrowser(zeroconf, SERVICE_TYPE, listener)
    
    print("\nLooking for your partner on the network...")
    time.sleep(5) # Wait 5 seconds for a service to be discovered

    server_url = listener.get_address(chat_code)
    stop_event = threading.Event()

    try:
        if server_url:
            # --- Client Mode ---
            print(f"Partner found! Connecting to {server_url}...")
            
            # Send my public key to the server and try to obtain the server's public key from the response
            server_pk = None
            if server_url and my_public_key:
                try:
                    import requests as _requests
                    resp = _requests.post(server_url + '/public_key', json={'public_key': base64.b64encode(my_public_key).decode('utf-8')}, timeout=5)
                    if resp.ok:
                        data = resp.json()
                        server_pk_b64 = data.get('server_public_key')
                        if server_pk_b64:
                            server_pk = base64.b64decode(server_pk_b64)
                except Exception:
                    pass

            # Fetch partner's public key if we didn't get it from the POST response
            if not server_pk:
                try:
                    response = requests.get(f"{server_url}/public_key")
                    partner_public_key = base64.b64decode(response.json().get('public_key'))
                except Exception:
                    partner_public_key = None
            else:
                partner_public_key = server_pk

            if not partner_public_key:
                print("Could not get partner's public key. Exiting.")
                return

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
                    # echo locally
                    display_message(full_message)
                    try:
                        requests.post(f"{server_url}/message", json={'message': base64.b64encode(encrypted_message).decode('utf-8')})
                    except requests.exceptions.RequestException:
                        print("Error: Could not connect to partner. Exiting.")
                        break
        
        else:
            # --- Server Mode ---
            print("No partner found. Starting in server mode and waiting for them to connect...")
            # Callback to print incoming messages immediately on the hosting side
            def on_msg(encrypted_bytes):
                try:
                    text = decrypt_message(encrypted_bytes, my_private_key)
                    display_message(text)
                except Exception as e:
                    logger.debug(f"Server on_msg error: {e}")

            server_info = run_server(zeroconf, name, chat_filename, my_public_key, on_message_callback=on_msg)
            
            print("\n--- E2EE Chat Started (Server Mode) ---")
            print("Type '.exit' to quit.")
            print("Waiting for client to connect and exchange keys...")

            # We'll use HTTP endpoints just like the client does
            server_base_url = f"http://127.0.0.1:{SERVER_PORT}"
            partner_pk = None
            
            while True:
                message = input("> ")
                if message.lower() == '.exit':
                    break
                if not message:
                    continue

                full_message = f"{name}: {message}"

                # Get peer's public key from our Flask server
                if not partner_pk:
                    try:
                        resp = requests.get(f"{server_base_url}/peer_public_key", timeout=2)
                        if resp.ok:
                            data = resp.json()
                            pk_b64 = data.get('public_key')
                            if pk_b64:
                                partner_pk = base64.b64decode(pk_b64)
                    except Exception:
                        pass

                if not partner_pk:
                    display_message("[local] Waiting for client to connect...")
                    continue

                try:
                    # Encrypt and send through our own /message endpoint (just like clients do)
                    encrypted_message = encrypt_message(full_message, partner_pk)
                    resp = requests.post(
                        f"{server_base_url}/message",
                        json={'message': base64.b64encode(encrypted_message).decode('utf-8')},
                        timeout=2
                    )
                    
                    if resp.ok:
                        display_message(f"[you] {full_message}")
                    else:
                        display_message("[local] Failed to send message")
                        
                except Exception as e:
                    display_message(f"[local] Error: {e}")

    finally:
        print("\nExiting Pychat. Goodbye!")
        stop_event.set()
        zeroconf.close()

if __name__ == "__main__":
    main()

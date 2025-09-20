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
from config import KEYS_DIR, CHATS_DIR, initialize_directories
from cleanerfile import ServiceListener, get_local_ip
import logging

# Set up logging
logger = logging.getLogger('pychat')


# --- Key Management Functions ---
# (These remain here as they involve direct user interaction via print)

kem = MLKEM_1024()
# hashes of encrypted payloads the local host wrote (so the file-watcher can ignore them)
sent_message_hashes = set()

def get_key_path(filename, keys_dir):
    """Get absolute path for a key file, ensuring the directory exists."""
    ensure_directory(keys_dir)
    return os.path.join(keys_dir, filename)

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
        
def save_key(key, key_type, keys_dir):
    """Save a key to the keys directory."""
    key_path = get_key_path(f"{key_type}.key", keys_dir)
    try:
        with open(key_path, 'wb') as f:
            f.write(key)
        os.chmod(key_path, 0o600)  # Secure permissions
        return key_path
    except Exception as e:
        print(f"Error saving {key_type} key: {e}")
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

def decrypt_message(encrypted_data, private_key, skip_errors=False):
    """Decrypts an incoming message.

    Args:
        encrypted_data: Either base64-encoded string/bytes (from network) or raw bytes (from file)
        private_key: The private key to use for decryption
        skip_errors: If True, returns None on error instead of raising
    """
    try:
        # normalize to raw bytes
        try:
            if isinstance(encrypted_data, (bytes, bytearray)):
                raw = bytes(encrypted_data)
            else:
                # assume it's a base64 string
                raw = base64.b64decode(encrypted_data)
        except Exception as e:
            logger.debug(f"Error normalizing message data: {e}")
            if skip_errors:
                return None
            raise ValueError("Invalid message format")

        # encapsulated key size from MLKEM params
        encaps_size = kem.param_sizes.ct_size
        verif_size = 160  # Krypton verification tag size
        min_size = encaps_size + verif_size

        # Check message size
        if len(raw) < min_size:
            err_msg = f"Message too short: {len(raw)} bytes (min {min_size} required)"
            logger.debug(err_msg)
            if skip_errors:
                return None
            raise ValueError(err_msg)

        try:
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
            logger.debug(f"Decryption error: {e}, message length: {len(raw)} bytes")
            if skip_errors:
                return None
            raise

    except Exception as e:
        logger.debug(f"Unexpected error in decrypt_message: {e}")
        if not skip_errors:
            raise

# --- Listener Functions ---

def display_message(text):
    """Display a message while preserving the input prompt. 
    
    Args:
        text: The message text to display
    """
    try:
        # Log the message
        logger.debug(f"Displaying message: {text}")
        
        # Get the current input line to preserve it
        try:
            import readline
            input_buffer = readline.get_line_buffer()
            cursor_pos = readline.get_begidx()  # Get cursor position
        except (ImportError, AttributeError):
            # Fallback if readline is not available
            input_buffer = ""
            cursor_pos = 0
        
        # Clear the current line and print the message
        print('\r' + ' ' * 80, end='\r')  # Clear the line
        print(text)  # Print the new message
        
        # Print the input prompt and restore any typed text
        if input_buffer:
            print(f"> {input_buffer}", end='', flush=True)
            # Move cursor back to the original position
            print(f"\033[{len(input_buffer) - cursor_pos + 2}D", end='', flush=True)
        else:
            print('> ', end='', flush=True)
            
    except Exception as e:
        # Fallback in case of any errors
        logger.error(f"Error in display_message: {e}")
        print(f"\n{text}")
        print('> ', end='', flush=True)
        print('> ', end='', flush=True)

def client_message_listener(stop_event, server_url, private_key, client_name):
    """Poll the server for new messages and display them.
    
    Args:
        stop_event: Event to signal when to stop listening
        server_url: Base URL of the server
        private_key: Private key for decrypting messages
        client_name: Name of the current client for filtering own messages
    """
    last_poll = time.time()
    consecutive_errors = 0
    max_consecutive_errors = 5
    seen_messages = set()
    
    # Start a simple HTTP server to receive messages from other clients
    def start_message_receiver():
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import json
        
        class MessageHandler(BaseHTTPRequestHandler):
            def _set_headers(self):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
            def do_POST(self):
                if self.path == '/client_message':
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    try:
                        data = json.loads(post_data)
                        encrypted_message_b64 = data.get('message')
                        if encrypted_message_b64:
                            try:
                                logger.debug(f"Received encrypted message (b64): {encrypted_message_b64[:50]}...")
                                encrypted_message = base64.b64decode(encrypted_message_b64)
                                logger.debug(f"Decoded message length: {len(encrypted_message)} bytes")
                                decrypted = decrypt_message(encrypted_message, private_key, skip_errors=True)
                                if decrypted:
                                    if not decrypted.startswith(f"{client_name}:"):
                                        logger.debug(f"Displaying decrypted message: {decrypted}")
                                        display_message(decrypted)
                                    else:
                                        logger.debug("Skipping own message")
                                else:
                                    logger.debug("Failed to decrypt message")
                            except Exception as e:
                                logger.error(f"Error processing message: {e}")
                    except Exception as e:
                        logger.error(f"Error handling incoming message: {e}")
                    
                    self._set_headers()
                    self.wfile.write(json.dumps({"status": "ok"}).encode())
                else:
                    self.send_error(404, "Not Found")
        
        server_address = ('', SERVER_PORT + 1)
        httpd = HTTPServer(server_address, MessageHandler)
        logger.debug(f"Starting message receiver on port {SERVER_PORT + 1}")
        
        # Run the server in a separate thread
        def run_server():
            while not stop_event.is_set():
                httpd.handle_request()
            
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        return server_thread
    
    # Start the message receiver
    start_message_receiver()
    
    # Register this client with the server
    try:
        # Get the local IP address for callback
        local_ip = get_local_ip()
        register_url = f"http://{local_ip}:{SERVER_PORT + 1}/client_message"
        
        requests.post(
            f"{server_url}/connect",
            json={'url': f"http://{local_ip}:{SERVER_PORT + 1}"},
            timeout=2
        )
        logger.debug(f"Registered client with server: {register_url}")
    except Exception as e:
        logger.error(f"Failed to register client with server: {e}")
    
    while not stop_event.is_set():
        try:
            # Poll server for new messages
            logger.debug(f"Polling for new messages since {last_poll}")
            response = None
            
            try:
                response = requests.get(
                    f"{server_url}/messages",
                    params={'since': last_poll},
                    timeout=2  # Increased timeout for better reliability
                )
                
                if response.status_code == 200:
                    try:
                        new_messages_b64 = response.json()
                        if new_messages_b64:
                            logger.debug(f"Received {len(new_messages_b64)} new messages")
                            
                            for encrypted_message_b64 in new_messages_b64:
                                if not encrypted_message_b64:
                                    logger.debug("Skipping empty message")
                                    continue
                                    
                                try:
                                    # Use a hash of the base64 string to uniquely identify messages
                                    msg_hash = hashlib.sha256(encrypted_message_b64.encode('utf-8')).hexdigest()
                                    
                                    # Skip duplicate messages
                                    if msg_hash in seen_messages:
                                        logger.debug("Skipping duplicate message")
                                        continue
                                        
                                    seen_messages.add(msg_hash)
                                    
                                    # Try to decrypt the message with error handling
                                    encrypted_message = base64.b64decode(encrypted_message_b64)
                                    decrypted = decrypt_message(encrypted_message, private_key, skip_errors=True)
                                    
                                    if decrypted:
                                        # Skip our own messages that might be echoed back
                                        if not decrypted.startswith(f"{client_name}:"):
                                            display_message(decrypted)
                                        consecutive_errors = 0  # Reset error counter on success
                                    else:
                                        logger.debug("Skipping undecryptable message")
                                        
                                except Exception as e:
                                    logger.error(f"Error processing message: {e}")
                                    
                            last_poll = time.time()  # Update last poll time on successful message processing
                            
                    except ValueError as e:
                        logger.error(f"Error parsing server response: {e}")
                        consecutive_errors += 1
                        
                else:
                    logger.error(f"Server returned status code {response.status_code}")
                    consecutive_errors += 1
                    
                # Reset error counter on successful request
                if response and response.status_code == 200:
                    consecutive_errors = 0
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    display_message("[System] Connection lost, attempting to reconnect...")
                    time.sleep(5)  # Longer delay after multiple errors
        
        except Exception as e:
            logger.debug(f"Unexpected error in client message listener: {e}")
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                display_message("[System] Connection error, retrying...")
                time.sleep(5)  # Longer delay after multiple errors
        
        time.sleep(0.5)  # Base delay between polls for more responsive updates

# --- Main Application ---

def ensure_directory(directory):
    """Ensure a directory exists, create it if it doesn't."""
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        os.chmod(directory, 0o755)  # Ensure proper permissions

def view_chat_history(chat_code):
    """
    Loads and decrypts chat history for a given chat code.
    """
    # Construct paths
    chat_file_path = os.path.join(CHATS_DIR, f"{chat_code}.txt")
    private_key_path = get_key_path(f"{chat_code}_private.key", KEYS_DIR)

    # --- 1. Load Private Key ---
    if not os.path.exists(private_key_path):
        print(f"Error: Private key for chat '{chat_code}' not found.")
        return
        
    private_key = load_private_key(private_key_path)
    if not private_key:
        return

    # --- 2. Read and Decrypt Chat File ---
    if not os.path.exists(chat_file_path):
        print(f"Error: Chat history for '{chat_code}' not found.")
        return

    print(f"\n--- Chat History for '{chat_code}' ---")
    
    try:
        with open(chat_file_path, "rb") as f:
            # Assuming each message is a base64 encoded string on a new line
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    # The file stores raw bytes, not base64 strings.
                    # We pass the raw bytes directly to the decrypt function.
                    decrypted_message = decrypt_message(line, private_key, skip_errors=True)
                    
                    if decrypted_message:
                        print(decrypted_message)
                    else:
                        # This could be a message encrypted with the other person's key
                        # For now, we'll just indicate an undecryptable message.
                        print("[Undecryptable message from partner]")

                except Exception as e:
                    logging.debug(f"Could not decrypt line: {e}")
                    print("[Error processing a message in history]")

    except Exception as e:
        print(f"Error reading chat file: {e}")

    print("--- End of History ---")

def main():
    # Create necessary directories
    initialize_directories()
    
    name = input("Enter your name: ")
    chat_code = input("Enter a unique Chat Code for this session: ")
    chat_filename = os.path.join(CHATS_DIR, f"{chat_code}.txt")
    
    # chat file is now managed by the server, no need to clear it here

    # Generate and save key pair
    my_public_key, my_private_key = kem.keygen()
    
    # Save keys to files
    save_key(my_private_key, f"{chat_code}_private", KEYS_DIR)
    save_key(my_public_key, f"{chat_code}_public", KEYS_DIR)
    
    # Set up key paths for later use
    private_key_path = get_key_path(f"{chat_code}_private.key", KEYS_DIR)

    # --- Peer Discovery ---
    zeroconf = Zeroconf()
    listener = ServiceListener()
    browser = ServiceBrowser(zeroconf, SERVICE_TYPE, listener)
    
    print("\nLooking for your partner on the network...")
    time.sleep(5) # Wait 5 seconds for a service to be discovered

    server_url = listener.get_address(chat_code)
    logger.debug(f"Got server URL: {server_url}")
    stop_event = threading.Event()

    try:
        if server_url:
            # --- Client Mode ---
            print(f"Partner found! Connecting to {server_url}...")
            logger.debug(f"Starting client with server URL: {server_url}")
            
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

            # Start the client message listener in a separate thread
            listener_thread = threading.Thread(
                target=client_message_listener,
                args=(stop_event, server_url, my_private_key, name),  # Pass the client name
                daemon=True
            )
            listener_thread.start()
            
            # Give the listener a moment to start
            time.sleep(1)

            print("\n--- E2EE Chat Started (Client Mode) ---")
            print("Type '.exit' to quit or '.history' to view past messages.")

            while True:
                message = input("> ")
                if message.lower() == '.exit':
                    break
                if message.lower() == '.history':
                    view_chat_history(chat_code)
                    continue
                if message:
                    full_message = f"{name}: {message}"
                    encrypted_message = encrypt_message(full_message, partner_public_key)
                    
                    # Record message hash and send
                    message_hash = hashlib.sha256(encrypted_message).hexdigest()
                    sent_message_hashes.add(message_hash)
                    
                    try:
                        resp = requests.post(
                            f"{server_url}/message",
                            json={'message': base64.b64encode(encrypted_message).decode('utf-8')},
                            timeout=2
                        )
                        if resp.ok:
                            display_message(full_message)
                        else:
                            display_message("[local] Failed to send message")
                    except requests.exceptions.RequestException as e:
                        print(f"Error: Could not connect to partner: {e}")
                        break
        
        else:
            # --- Server Mode ---
            print("No partner found. Starting in server mode and waiting for them to connect...")

            # Define callback for incoming messages
            def on_message(encrypted_bytes):
                try:
                    h = hashlib.sha256(encrypted_bytes).hexdigest()
                    if h in sent_message_hashes:
                        sent_message_hashes.discard(h)
                        return
                        
                    text = decrypt_message(encrypted_bytes, my_private_key)
                    if text:
                        display_message(text)
                except Exception as e:
                    logger.debug(f"Server callback error: {e}")

            # Start server with callback for immediate message display
            server_info = run_server(zeroconf, name, chat_filename, my_public_key, on_message_callback=on_message)
            server_base_url = f"http://127.0.0.1:{SERVER_PORT}"

            print("\n--- E2EE Chat Started (Server Mode) ---")
            print("Type '.exit' to quit or '.history' to view past messages.")
            print("Waiting for client to connect and exchange keys...")
            
            while True:
                message = input("> ")
                if message.lower() == '.exit':
                    break
                if message.lower() == '.history':
                    view_chat_history(chat_code)
                    continue
                if not message:
                    continue

                # Try to get peer's public key from our server
                try:
                    resp = requests.get(f"{server_base_url}/peer_public_key", timeout=2)
                    if not resp.ok:
                        display_message("[local] Waiting for client to connect...")
                        continue

                    data = resp.json()
                    pk_b64 = data.get('public_key')
                    if not pk_b64:
                        display_message("[local] No client public key available yet")
                        continue

                    partner_pk = base64.b64decode(pk_b64)
                    
                    # Encrypt the message
                    full_message = f"{name}: {message}"
                    encrypted_message = encrypt_message(full_message, partner_pk)
                    
                    # Record hash to avoid echo
                    message_hash = hashlib.sha256(encrypted_message).hexdigest()
                    sent_message_hashes.add(message_hash)
                    
                    # Post the message to our /message endpoint
                    try:
                        logger.debug(f"Sending message to {server_base_url}/message")
                        message_data = base64.b64encode(encrypted_message).decode('utf-8')
                        logger.debug(f"Encoded message size: {len(message_data)} bytes")
                        
                        resp = requests.post(
                            f"{server_base_url}/message",
                            json={'message': message_data},
                            timeout=2
                        )
                        if resp.ok:
                            display_message(full_message)
                            logger.debug("Message sent successfully")
                        else:
                            display_message("[local] Failed to send message")
                            logger.debug(f"Server rejected message: {resp.status_code} - {resp.text}")
                    except Exception as e:
                        display_message(f"[local] Error: {e}")
                        logger.debug(f"Error sending message: {str(e)}")
                        time.sleep(1)
                        
                except Exception as e:
                    display_message(f"[local] Error: {e}")
                    time.sleep(1)

    finally:
        print("\nExiting Pychat. Goodbye!")
        stop_event.set()
        zeroconf.close()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.WARNING,  # Changed from DEBUG to WARNING to reduce output
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('pychat.log')
        ]
    )
    logger = logging.getLogger('pychat')
    logger.info("Starting PyChat...")
    
    try:
        main()
    except Exception as e:
        logger.exception("Unhandled exception in main:")
        raise

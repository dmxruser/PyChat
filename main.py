import os
import time
import threading
import base64
import random
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

# Made with the assistance of AI

# --- Key Management Functions ---

def generate_and_save_keys():
    """Generates a private/public key pair with random filenames and saves them."""
    print("\nGenerating new key pair...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()

    # Generate a random code for the filenames
    code = str(random.randint(100000, 999999))
    private_key_filename = f"private_{code}.key"
    public_key_filename = f"public_{code}.key"

    # Save private key
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(private_key_filename, "wb") as f:
        f.write(pem_private)
    
    # Save public key
    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    with open(public_key_filename, "wb") as f:
        f.write(pem_public)
    
    print("\n--- New Keys Generated ---")
    print(f"Your new private key is saved as: {private_key_filename} (KEEP THIS SECRET)")
    print(f"Your new public key is saved as: {public_key_filename} (share this one with your partner)")
    print("--------------------------\n")

def load_private_key(key_path):
    """Loads the user's private key from a given path."""
    try:
        with open(key_path, "rb") as f:
            private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
            )
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
            public_key = serialization.load_pem_public_key(f.read())
        return public_key
    except FileNotFoundError:
        print(f"Error: Public key file not found at '{key_path}'.")
        return None
    except Exception as e:
        print(f"Error loading public key: {e}")
        return None

# --- Core Chat Functions ---

def encrypt_message(message, public_key):
    """Encrypts a message using the partner's public key."""
    encrypted = public_key.encrypt(
        message.encode('utf-8'),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return base64.b64encode(encrypted)

def decrypt_message(encrypted_message, private_key):
    """Decrypts a message using the user's private key."""
    decoded_message = base64.b64decode(encrypted_message)
    decrypted = private_key.decrypt(
        decoded_message,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return decrypted.decode('utf-8')

def message_listener(private_key, chat_filename, stop_event):
    """Runs in a background thread, checking for and displaying new messages."""
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

    # --- Start Listener Thread ---
    stop_event = threading.Event()
    listener = threading.Thread(target=message_listener, args=(my_private_key, chat_filename, stop_event), daemon=True)
    listener.start()

    print("\n--- E2EE Chat Started ---")
    print("Type '.exit' to quit.")
    
    # --- Main Loop for Sending Messages ---
    try:
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

if __name__ == "__main__":
    main()

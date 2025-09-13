# PyChat - Secure Peer-to-Peer Chat Application

A secure, encrypted chat application that works over local networks using Python and Podman/Docker.

## Prerequisites

- Podman (or Docker)
- Python 3.11+

## Quick Start with Podman

1. **Build the container image**:
   ```bash
   podman build -t pychat .
   ```

2. **Run the chat application**:
   ```bash
   ./podman-run.sh
   ```
   Or manually:
   ```bash
   mkdir -p ./data ./keys
   podman run -it --rm \
     --name pychat \
     --network=host \
     -v ./data:/app/data:Z \
     -v ./keys:/app/keys:Z \
     pychat
   ```

## How It Works

1. **First User (Server)**:
   - Enter your name and a chat code
   - The application will start in server mode
   - Share the chat code with the person you want to chat with

2. **Second User (Client)**:
   - Enter your name and the same chat code
   - The application will automatically discover and connect to the server on the local network

## Security Features

- End-to-end encryption using ML-KEM-1024
- Secure key exchange
- Message authentication
- Local network discovery

## Directory Structure

- `/app/data` - Chat logs and temporary files
- `/app/keys` - Encryption keys (keep this secure!)

## Troubleshooting

- If you get permission errors, try running with `--privileged` flag
- Make sure both users are on the same local network
- Check that the required ports are not blocked by your firewall

## License

This project is licensed under the MIT License - see the LICENSE file for details.

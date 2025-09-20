#!/bin/bash

# Exit on error
set -e

# Create directories if they don't exist
mkdir -p ./data ./keys
chmod 755 ./data ./keys

# Build the container image
podman build -t pychat .

# Create a podman network if it doesn't exist
if ! podman network exists pychat-network; then
    podman network create pychat-network
fi

# Run the container with the current directory mounted
podman run -it --rm \
  --name pychat \
  --network=pychat-network \
  -p 5000-5001:5000-5001 \
  -e PYCHAT_BASE_DIR=/app \
  -v ./data:/app/data:Z \
  -v ./keys:/app/keys:Z \
  pychat

# Clean up on exit
cleanup() {
  echo "Cleaning up..."
  podman stop pychat 2>/dev/null || true
  podman rm pychat 2>/dev/null || true
}
trap cleanup EXIT

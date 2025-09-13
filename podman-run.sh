#!/bin/bash

# Exit on error
set -e

# Create directories if they don't exist
mkdir -p ./data ./keys
chmod 755 ./data ./keys

# Build the container image
podman build -t pychat .

# Run the container with the current directory mounted
podman run -it --rm \
  --name pychat \
  --network=host \
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

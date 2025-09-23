#!/bin/bash
if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root."
  echo "Please use 'sudo ./post_install.sh'"
  exit 1
fi

echo "Checking for /etc/QuanCha..."
if [ ! -d "/etc/QuanCha" ]; then
  echo "Creating /etc/QuanCha directory..."
  mkdir -p /etc/QuanCha
else
  echo "/etc/QuanCha already exists."
fi

echo "Checking for certs..."
if [ ! -f "/etc/QuanCha/cert.pem" ] || [ ! -f "/etc/QuanCha/key.pem" ]; then
  echo "Generating new certificates..."
  openssl req -x509 -newkey rsa:2048 -keyout /etc/QuanCha/key.pem -out /etc/QuanCha/cert.pem -days 365 -nodes -subj "/CN=localhost"
else
  echo "Certs already exist. Generate new keys? [y/N]"
  read -r answer
  if [[ "$answer" =~ ^[Yy]$ ]]; then
    echo "Generating new certificates..."
    openssl req -x509 -newkey rsa:2048 -keyout /etc/QuanCha/key.pem -out /etc/QuanCha/cert.pem -days 365 -nodes -subj "/CN=localhost"
  else
    echo "Skipping cert generation."
  fi
fi

echo "Post-install script finished."
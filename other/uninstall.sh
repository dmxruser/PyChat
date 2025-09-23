#!/bin/bash
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root."
  echo "Please use 'sudo ./uninstall.sh'"
  exit 1
fi

echo ">>> Removing QuanCha application files..."

if [ -f "/usr/local/bin/QuanCha" ]; then
    echo "Removing executable..."
    rm -f "/usr/local/bin/QuanCha"
fi

if [ -f "/usr/share/pixmaps/QuanCha.svg" ]; then
    echo "Removing icon..."
    rm -f "/usr/share/pixmaps/QuanCha.svg"
fi

if [ -f "/usr/share/applications/QuanCha.desktop" ]; then
    echo "Removing desktop file..."
    rm -f "/usr/share/applications/QuanCha.desktop"
fi

if [ -d "/opt/QuanCha" ]; then
    echo "Removing installation directory..."
    rm -rf "/opt/QuanCha"
fi

if [ -d "/etc/QuanCha" ]; then
    echo "Removing certificates directory..."
    rm -rf "/etc/QuanCha"
fi

echo ">>> QuanCha uninstallation complete!"

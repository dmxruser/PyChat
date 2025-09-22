#!/bin/bash
if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root."
  echo "Please use '''sudo ./install.sh'''"
  exit 1
fi

echo ">>> Cloning the QuanCha repository..."

REPO_URL="https://github.com/dmxruser/QuanCha.git"
TMP_DIR=$(mktemp -d)

echo "Cloning from $REPO_URL into $TMP_DIR"
git clone --depth 1 "$REPO_URL" "$TMP_DIR"
if [ $? -ne 0 ]; then
    echo "Error: Failed to clone the repository."
    exit 1
fi
cd "$TMP_DIR"

echo ">>> Checking operating system and package manager..."

if command -v apt-get &> /dev/null; then
    PACKAGE_MANAGER="apt"
elif command -v dnf &> /dev/null; then
    PACKAGE_MANAGER="dnf"
elif command -v pacman &> /dev/null; then
    PACKAGE_MANAGER="pacman"
else
    echo "Error: Could not detect a supported package manager (apt, dnf, or pacman)."
    exit 1
fi

echo ">>> Detected package manager: $PACKAGE_MANAGER. Installing dependencies..."

case $PACKAGE_MANAGER in
    "apt")
        apt-get update
        apt-get install -y git python3 python3-pip python3-venv
        ;;
    "dnf")
        dnf install -y git python3 python3-pip python3-virtualenv
        ;;
    "pacman")
        pacman -Syu --noconfirm git python python-pip python-virtualenv
        ;;
esac

if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
else
    echo "Error: requirements.txt not found."
    exit 1
fi

# Install PyInstaller
pip3 install pyinstaller

echo ">>> Dependencies installed successfully."

echo ">>> Building the standalone application with PyInstaller..."

pyinstaller \
    --name QuanCha \
    --onefile \
    --windowed \
    --add-data "qt/Main.qml:qt" \
    --add-data "qt/chat.qml:qt" \
    --add-data "qt/discovery.qml:qt" \
    --add-data "QuanCha.svg:." \
    qt/qt.py

if [ ! -f "dist/QuanCha" ]; then
    echo "Error: PyInstaller build failed."
    exit 1
fi

echo ">>> Application built successfully."

echo ">>> Installing application files system-wide..."

mkdir -p /usr/local/bin
mkdir -p /usr/share/pixmaps
mkdir -p /usr/share/applications

cp dist/QuanCha /usr/local/bin/
cp QuanCha.svg /usr/share/pixmaps/

# Create and install the .desktop file
cat > /usr/share/applications/QuanCha.desktop <<EOL
[Desktop Entry]
Version=1.0
Name=QuanCha
Comment=A quantum-resistant Python/QML Chat Application.
Exec=/usr/local/bin/QuanCha
Icon=/usr/share/pixmaps/QuanCha.svg
Terminal=false
Type=Application
Categories=Network;InstantMessaging;
EOL

echo "------------------------------------------------"
echo ">>> QuanCha installation complete!"
echo "------------------------------------------------"
echo "You can now find 'QuanCha' in your application menu."

# --- 7. Cleanup ---
echo ">>> Cleaning up temporary files..."
rm -rf "$TMP_DIR"

echo "Done."
exit 0

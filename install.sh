#!/bin/bash
if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root."
  echo "Please use 'sudo ./install.sh'"
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
elif command -v zypper &> /dev/null; then
    PACKAGE_MANAGER="zypper"
else
    echo "Error: Could not detect a supported package manager (apt, dnf, pacman, or zypper)."
    exit 1
fi

echo ">>> Detected package manager: $PACKAGE_MANAGER. Installing dependencies..."

# The 'sudo' is not needed here as the script is already running as root.
case "$PACKAGE_MANAGER" in
    "apt")
        apt-get update
        apt-get install -y git python3 python3-dev qt6-declarative-dev
        ;;
    "dnf")
        dnf install -y git python3 python3-devel qt6-qtdeclarative-devel
        ;;
    "pacman")
        pacman -Syu --noconfirm git python qt6-declarative
        ;;
    "zypper")
        zypper install -y git python3 python3-devel libQt6Declarative-devel
        ;;
    *)
        echo "Unsupported package manager: $PACKAGE_MANAGER"
        exit 1
        ;;
esac

# Check for pip3 and install it if it's not present.
if ! command -v pip3 &> /dev/null; then
    echo "pip3 is not installed. Attempting to install it now."
    case "$PACKAGE_MANAGER" in
        "apt")
            apt-get install -y python3-pip
            ;;
        "dnf")
            dnf install -y python3-pip
            ;;
        "pacman")
            pacman -Syu --noconfirm python-pip
            ;;
        "zypper")
            zypper install -y python3-pip
            ;;
    esac
fi

echo ">>> Installing Python dependencies with pip..."
# PyInstaller is necessary for the build process
# We're also adding 'requests' and 'zeroconf' which were missing
# The '--break-system-packages' flag is used to force installation in system-wide environment
pip3 install pyinstaller requests zeroconf quantcrypt --break-system-packages

if [ $? -ne 0 ]; then
    echo "Error: Failed to install Python dependencies with pip."
    echo "Please ensure pip is configured correctly."
    exit 1
fi

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

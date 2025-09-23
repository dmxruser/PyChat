#!/bin/bash
set -e

# --- Configuration ---
INSTALL_DIR="/opt/QuanCha"
VENV_DIR="$INSTALL_DIR/venv"
EXECUTABLE_PATH="/usr/local/bin/QuanCha"

# --- Cleanup on Exit ---
function cleanup() {
    if [ -d "$TMP_DIR" ]; then
        echo ">>> Cleaning up temporary files..."
        rm -rf "$TMP_DIR"
    fi
}
trap cleanup EXIT

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

case "$PACKAGE_MANAGER" in
    "apt")
        apt-get update
        apt-get install -y git python3 python3-dev python3-venv qt6-declarative-dev
        ;;
    "dnf")
        dnf install -y git python3 python3-devel python3-virtualenv qt6-qtdeclarative-devel
        ;;
    "pacman")
        pacman -Syu --noconfirm git python python-virtualenv qt6-declarative
        ;;
    "zypper")
        zypper install -y git python3 python3-devel python3-virtualenv libQt6Declarative-devel
        ;;
    *)
        echo "Unsupported package manager: $PACKAGE_MANAGER"
        exit 1
        ;;
esac

echo ">>> Creating installation directory at $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

echo ">>> Creating Python virtual environment at $VENV_DIR..."
python3 -m venv "$VENV_DIR"

echo ">>> Activating virtual environment and installing Python dependencies..."
source "$VENV_DIR/bin/activate"

# We need to upgrade pip in the venv
pip install --upgrade pip

# Now install all the python dependencies from requirements.txt and PySide6
pip install -r requirements.txt
pip install PySide6
pip install pyinstaller

echo ">>> Copying application files to $INSTALL_DIR..."
# Copy all files from the cloned repo to the installation directory
# We use rsync to avoid copying the .git directory
rsync -a --exclude '.git' . "$INSTALL_DIR/"

echo ">>> Building the standalone application with PyInstaller..."

# Dynamically find the site-packages directory
SITE_PACKAGES_DIR=$("$VENV_DIR/bin/python" -c "import site; print(site.getsitepackages()[0])")

# Run pyinstaller from within the venv
"$VENV_DIR/bin/pyinstaller" \
    --name QuanCha \
    --onefile \
    --windowed \
    --paths "$SITE_PACKAGES_DIR" \
    --hidden-import="PySide6.QtNetwork" \
    --hidden-import="PySide6.QtCore" \
    --hidden-import="PySide6.QtGui" \
    --hidden-import="PySide6.QtWidgets" \
    --hidden-import="PySide6.QtQml" \
    --hidden-import="zeroconf" \
    --hidden-import="requests" \
    --add-data "$INSTALL_DIR/qt/Main.qml:qt" \
    --add-data "$INSTALL_DIR/qt/chat.qml:qt" \
    --add-data "$INSTALL_DIR/qt/discovery.qml:qt" \
    --add-data "$INSTALL_DIR/QuanCha.svg:." \
    "$INSTALL_DIR/qt/qt.py"

if [ ! -f "dist/QuanCha" ]; then
    echo "Error: PyInstaller build failed."
    exit 1
fi

echo ">>> Application built successfully."

echo ">>> Installing application files system-wide..."

cp "dist/QuanCha" "/usr/local/bin/"
cp "$INSTALL_DIR/QuanCha.svg" "/usr/share/pixmaps/"

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

echo ">>> Running post-installation script..."
if [ -f "$INSTALL_DIR/other/post_install.sh" ]; then
    chmod +x "$INSTALL_DIR/other/post_install.sh"
    "$INSTALL_DIR/other/post_install.sh"
else
    echo "Warning: other/post_install.sh not found. Skipping certificate setup."
fi

echo "------------------------------------------------"
echo ">>> QuanCha installation complete!"
echo "------------------------------------------------"
echo "You can now find 'QuanCha' in your application menu."

echo "Done."
exit 0
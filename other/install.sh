#!/bin/bash
set -e

# --- Configuration ---
APP_NAME="QuanCha"
INSTALL_DIR="/opt/$APP_NAME"
VENV_DIR="$INSTALL_DIR/venv"
EXECUTABLE_PATH="/usr/local/bin/$APP_NAME"
DESKTOP_FILE="/usr/share/applications/$APP_NAME.desktop"
ICON_DIR="/usr/share/pixmaps"

# --- Colors for output ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- Helper functions ---
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "This script must be run as root. Please use 'sudo $0'"
    fi
}

install_dependencies() {
    info "Installing system dependencies..."
    
    if command -v apt-get &> /dev/null; then
        apt-get update
        apt-get install -y python3 python3-pip python3-venv python3-dev \
                         python3-wheel python3-setuptools \
                         qt6-declarative-dev \
                         build-essential \
                         libssl-dev \
                         libffi-dev
    elif command -v dnf &> /dev/null; then
        dnf install -y python3 python3-pip python3-virtualenv python3-devel \
                     qt6-qtdeclarative-devel \
                     @development-tools \
                     openssl-devel \
                     libffi-devel
    elif command -v pacman &> /dev/null; then
        pacman -Syu --noconfirm python python-pip python-virtualenv \
                               qt6-declarative \
                               base-devel \
                               openssl \
                               libffi
    elif command -v zypper &> /dev/null; then
        zypper install -y python3 python3-pip python3-virtualenv \
                        python3-devel \
                        libqt6-qtdeclarative-devel \
                        patterns-devel-base-devel_basis \
                        libopenssl-devel \
                        libffi-devel
    else
        warn "Could not detect a supported package manager. You'll need to install dependencies manually."
    fi
}

create_virtualenv() {
    info "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR" || error "Failed to create virtual environment"
    
    # Activate the virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Upgrade pip and setuptools
    pip install --upgrade pip setuptools wheel
}

install_python_deps() {
    info "Installing Python dependencies..."
    
    # Install quantcrypt first with --no-cache-dir
    pip install --no-cache-dir quantcrypt || error "Failed to install quantcrypt"
    
    # Install other dependencies
    pip install -r requirements.txt || error "Failed to install requirements"
    pip install PySide6 || error "Failed to install PySide6"
    pip install pyinstaller || error "Failed to install PyInstaller"
}

build_application() {
    info "Building application with PyInstaller..."
    
    # Create a spec file for PyInstaller
    cat > "$INSTALL_DIR/$APP_NAME.spec" << 'EOL'
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['qt/qt.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('qt/*.qml', 'qt'),
        ('QuanCha.svg', '.')
    ],
    hiddenimports=[
        'PySide6.QtNetwork',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtQml',
        'zeroconf',
        'requests',
        'quantcrypt',
        'quantcrypt.internal',
        'quantcrypt.internal.bin',
        'behind',
        'behind.config',
        'behind.discovery',
        'behind.network',
        'behind.main'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='QuanCha',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
EOL
    
    # Build the application
    cd "$INSTALL_DIR"
    "$VENV_DIR/bin/pyinstaller" --clean --noconfirm "$APP_NAME.spec" || error "PyInstaller build failed"
    
    # Create a wrapper script
    cat > "$EXECUTABLE_PATH" << 'EOL'
#!/bin/bash
# Wrapper script for QuanCha

# Activate the virtual environment
source /opt/QuanCha/venv/bin/activate

# Run the application
exec /opt/QuanCha/dist/QuanCha "$@"
EOL
    
    chmod +x "$EXECUTABLE_PATH"
}

create_desktop_file() {
    info "Creating desktop file..."
    
    mkdir -p "$(dirname "$DESKTOP_FILE")"
    mkdir -p "$ICON_DIR"
    
    # Copy the icon
    cp "$INSTALL_DIR/QuanCha.svg" "$ICON_DIR/"
    
    # Create the desktop file
    cat > "$DESKTOP_FILE" << EOL
[Desktop Entry]
Version=1.0
Type=Application
Name=QuanCha
Comment=A quantum-resistant chat application
Exec=$EXECUTABLE_PATH
Icon=$ICON_DIR/QuanCha.svg
Terminal=false
Categories=Network;InstantMessaging;
EOL
    
    chmod +x "$DESKTOP_FILE"
}

# --- Main installation process ---

# Check if running as root
check_root

# Create installation directory
info "Creating installation directory at $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

# Copy files to installation directory
info "Copying application files..."
cp -r . "$INSTALL_DIR/"

# Change to installation directory
cd "$INSTALL_DIR"

# Install system dependencies
install_dependencies

# Create and set up virtual environment
create_virtualenv

# Install Python dependencies
install_python_deps

# Build the application
build_application

# Create desktop file
create_desktop_file

# Run post-installation script
if [ -f "$INSTALL_DIR/other/post_install.sh" ]; then
    info "Running post-installation script..."
    chmod +x "$INSTALL_DIR/other/post_install.sh"
    "$INSTALL_DIR/other/post_install.sh"
fi

info "\n${GREEN}Installation completed successfully!${NC}"
echo "You can now run QuanCha from your applications menu or by typing 'QuanCha' in the terminal."
echo "------------------------------------------------"
echo "You can now find 'QuanCha' in your application menu."

echo "Done."
exit 0
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
                         libffi-dev \
                         rsync
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
    
    # Create default requirements.txt if it doesn't exist
    if [ ! -f "$INSTALL_DIR/requirements.txt" ]; then
        warn "requirements.txt not found, creating default..."
        cat > "$INSTALL_DIR/requirements.txt" << 'EOL'
quantcrypt
zeroconf
requests
flask
PySide6
pyinstaller
EOL
        info "Created default requirements.txt in $INSTALL_DIR"
    fi
    
    # Install quantcrypt first with --no-cache-dir
    info "Installing quantcrypt..."
    pip install --no-cache-dir quantcrypt || error "Failed to install quantcrypt"
    
    # Install other dependencies
    info "Installing dependencies from requirements.txt..."
    pip install -r "$INSTALL_DIR/requirements.txt" || error "Failed to install requirements"
    
    # Ensure PySide6, PyInstaller and Pydantic are installed
    info "Ensuring PySide6 and PyInstaller are installed..."
    pip install PySide6 || error "Failed to install PySide6"
    pip install "pyinstaller>=6.10,<7" || error "Failed to install PyInstaller"
    pip install pydantic || error "Failed to install pydantic"
}

build_application() {
    info "Building application with PyInstaller..."
    
    # Build using PyInstaller CLI with explicit collection of quantcrypt assets
    cd "$INSTALL_DIR"

    # Create a local hook directory and hook for quantcrypt to force inclusion
    HOOKS_DIR="$INSTALL_DIR/other/hooks"
    mkdir -p "$HOOKS_DIR"
    cat > "$HOOKS_DIR/hook-quantcrypt.py" << 'PYIHOOK'
from PyInstaller.utils.hooks import collect_all, collect_submodules
datas, binaries, hiddenimports = collect_all('quantcrypt')
d2, b2, h2 = collect_all('quantcrypt.internal.bin')
datas += d2
binaries += b2
hiddenimports += h2
hiddenimports += collect_submodules('quantcrypt.internal.bin')
PYIHOOK
    
    # Ensure we have write permissions in the installation directory
    chmod -R u+w "$INSTALL_DIR"
    
    # Verify the source file exists
    if [ ! -f "$INSTALL_DIR/qt/qt.py" ]; then
        error "Source file not found: $INSTALL_DIR/qt/qt.py"
    fi
    
    info "Building from directory: $(pwd)"
    info "Using Python: $(which python3)"
    info "Using PyInstaller: $("$VENV_DIR/bin/pyinstaller" --version)"
    
    "$VENV_DIR/bin/pyinstaller" \
        --clean --noconfirm --log-level=DEBUG \
        --name "$APP_NAME" \
        --distpath "$INSTALL_DIR/dist" \
        --workpath "$INSTALL_DIR/build" \
        --additional-hooks-dir "$HOOKS_DIR" \
        --add-data "$INSTALL_DIR/QuanCha.svg:." \
        --add-data "$INSTALL_DIR/qt/*.qml:qt" \
        --collect-all quantcrypt \
        --collect-all quantcrypt.internal.bin \
        --collect-binaries quantcrypt \
        --collect-binaries quantcrypt.internal.bin \
        --collect-submodules quantcrypt \
        --collect-submodules quantcrypt.internal \
        --collect-submodules quantcrypt.internal.bin \
        --hidden-import PySide6.QtNetwork \
        --hidden-import PySide6.QtCore \
        --hidden-import PySide6.QtGui \
        --hidden-import PySide6.QtWidgets \
        --hidden-import PySide6.QtQml \
        --hidden-import quantcrypt \
        --hidden-import quantcrypt.internal \
        --hidden-import quantcrypt.internal.bin \
        --hidden-import quantcrypt.internal.bin.ml_kem_1024_avx2 \
        --hidden-import quantcrypt.internal.bin.ml_kem_1024_clean \
        --hidden-import quantcrypt.internal.bin.ml_kem_1024_ref \
        --collect-qt-plugins qml \
        --collect-qt-plugins network \
        "$INSTALL_DIR/qt/qt.py" \
        || {
            warn "PyInstaller build failed; falling back to running from sources in venv"
            # Show the last 50 lines of the build log for debugging if present
            if [ -f "$INSTALL_DIR/build/$APP_NAME/warn-$APP_NAME.txt" ]; then
                error "Last 50 lines of build log:"
                tail -n 50 "$INSTALL_DIR/build/$APP_NAME/warn-$APP_NAME.txt" >&2
            fi
        }

    # Fallback: if onedir build exists but quantcrypt binaries aren't there, copy from site-packages
    if [ -d "$INSTALL_DIR/dist/$APP_NAME" ]; then
        if [ ! -d "$INSTALL_DIR/dist/$APP_NAME/quantcrypt/internal/bin" ]; then
            info "quantcrypt binaries not found in dist; copying from site-packages..."
            QCRYPT_DIR="$($VENV_DIR/bin/python -c 'import quantcrypt, os; print(os.path.dirname(quantcrypt.__file__))' 2>/dev/null || true)"
            if [ -n "$QCRYPT_DIR" ] && [ -d "$QCRYPT_DIR/internal/bin" ]; then
                mkdir -p "$INSTALL_DIR/dist/$APP_NAME/quantcrypt/internal/bin"
                cp -a "$QCRYPT_DIR/internal/bin/." "$INSTALL_DIR/dist/$APP_NAME/quantcrypt/internal/bin/" || warn "Failed to copy quantcrypt binaries"
            else
                warn "Could not locate quantcrypt/internal/bin in site-packages ($QCRYPT_DIR)"
            fi
        fi
    fi
    
    # Create a wrapper script
    cat > "$EXECUTABLE_PATH" << 'EOL'
#!/bin/bash
# Wrapper script for QuanCha

# Activate the virtual environment
source /opt/QuanCha/venv/bin/activate

# Determine onedir vs onefile
if [ -x "/opt/QuanCha/dist/QuanCha/QuanCha" ]; then
  # onedir layout
  exec "/opt/QuanCha/dist/QuanCha/QuanCha" "$@"
elif [ -x "/opt/QuanCha/dist/QuanCha" ]; then
  # onefile layout
  exec "/opt/QuanCha/dist/QuanCha" "$@"
elif [ -f "/opt/QuanCha/qt/qt.py" ]; then
  # Fallback: run from sources inside venv
  exec python "/opt/QuanCha/qt/qt.py" "$@"
else
  echo "QuanCha binary not found in dist/. Please reinstall." >&2
  exit 1
fi
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

# Get the absolute path of the project root (one level up from the 'other' directory)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Copy files to installation directory
info "Copying application files from $PROJECT_ROOT to $INSTALL_DIR..."
# Create the installation directory if it doesn't exist
mkdir -p "$INSTALL_DIR"
# Copy all files except the venv directory if it exists
if command -v rsync >/dev/null 2>&1; then
    rsync -a --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' "$PROJECT_ROOT/" "$INSTALL_DIR/" || error "Failed to copy application files"
else
    warn "rsync not found, falling back to cp -a"
    cp -a "$PROJECT_ROOT"/. "$INSTALL_DIR"/ || error "Failed to copy application files"
fi

# Change to installation directory
cd "$INSTALL_DIR"
info "Current directory: $(pwd)"

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
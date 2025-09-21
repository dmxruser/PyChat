# PyChat

A secure chat application with a Qt-based frontend and Python backend.

## Features

- Secure messaging between users
- Qt-based graphical user interface
- Service discovery using Zeroconf
- Message history
- User settings

## Requirements

- Python 3.8+
- PySide6
- Flask
- python-zeroconf
- cryptography

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Pychat
   ```

2. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

### Qt Frontend

To run the Qt-based frontend:

```bash
python qt/qt.py
```

### Command Line Interface

You can also run the application in server or client mode from the command line:

```bash
# Server mode
python -m behind.main server_mode

# Client mode
python -m behind.main client_mode --server-ip <server-ip>
```

## Project Structure

- `qt/` - Qt frontend code
  - `qt.py` - Main Qt application entry point
  - `Main.qml` - QML UI definition
- `behind/` - Backend code
  - `__init__.py` - Package initialization
  - `main.py` - Main application logic
  - `network.py` - Network communication
  - `discovery.py` - Service discovery
  - `config.py` - Configuration settings

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

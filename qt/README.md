# PyChat Qt Setup

This project is set up to work with Qt Creator for Python/QML development.

## Project Structure

```
/home/dmxruser/devcrap/Pychat/
├── PyChat.pro          # Main Qt Creator project file
├── qt/
│   ├── qt.py          # Python application entry point
│   └── Main.qml       # QML user interface
├── requirements.txt    # Python dependencies
├── Makefile           # Build automation
└── README.md          # This file
```

## How to Use with Qt Creator

1. Open `PyChat.pro` in Qt Creator
2. The project includes:
   - Python source files (`qt/qt.py`)
   - QML interface files (`qt/Main.qml`)
   - Run configuration to launch the application
   - Clean targets for Python cache files

## Available Targets

- **Run**: Launch the PyChat application
- **Clean Cache**: Remove Python cache files (`__pycache__`, `*.pyc`)
- **Install Dependencies**: Install Python packages from `requirements.txt`

## Development

The project uses PySide6 for Qt integration with Python. The QML interface communicates with the Python backend through Qt's signal/slot mechanism.

.PHONY: run install-deps clean

# Python executable
PYTHON = python3
PIP = pip3

# Directories
QT_DIR = qt
BACKEND_DIR = behind

# Main application file
QT_APP = $(QT_DIR)/qt.py

# Dependencies
REQUIREMENTS = requirements.txt

# Default target
all: run

# Install Python dependencies
install-deps:
	$(PIP) install PySide6 flask python-zeroconf cryptography

# Run the Qt application
run: install-deps
	PYTHONPATH=$(PWD) $(PYTHON) $(QT_APP)

# Clean generated files
clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete

# Help target
help:
	@echo "Available targets:"
	@echo "  run         - Run the Qt application (default)"
	@echo "  install-deps - Install Python dependencies"
	@echo "  clean       - Remove generated files"
	@echo "  help        - Show this help message"

# Set the default target
.DEFAULT_GOAL := run

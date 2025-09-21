# PyChat - Python/QML Chat Application
# Main Qt Creator project file

TEMPLATE = app
TARGET = PyChat

# Python configuration
PYTHON = python3
PYTHONPATH = $$PWD

# Qt modules for QML support
QT += qml quick

# Include Python and QML files
PYTHON_SOURCES += qt/qt.py
QML_FILES += qt/Main.qml

# Additional project files
OTHER_FILES += \
    qt/qt.py \
    qt/Main.qml \
    requirements.txt \
    Makefile \
    README.md

# Set working directory
DESTDIR = $$PWD

# Run configuration
QMAKE_EXTRA_TARGETS += run
run.commands = cd $$PWD && $$PYTHON qt/qt.py
run.target = run

# Add run target to default
first: run

# Clean up Python cache
QMAKE_EXTRA_TARGETS += clean_cache
clean_cache.commands = find $$PWD -name "__pycache__" -exec rm -rf {} + && find $$PWD -name "*.pyc" -delete

# Install dependencies
QMAKE_EXTRA_TARGETS += install_deps
install_deps.commands = $$PYTHON -m pip install -r requirements.txt

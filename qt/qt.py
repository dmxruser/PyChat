import os
import sys
import logging
from datetime import datetime
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtQuick import QQuickView
from PySide6.QtCore import QUrl, QObject, Signal, Slot, Property, QTimer
from PySide6.QtQml import QQmlApplicationEngine

# Import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from behind import NetworkManager
from behind.config import initialize_directories
from behind import main

# variables for qml
class NameModel(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._name = ""

    @Signal
    def nameChanged(self):
        pass

    @Property(str, notify=nameChanged)
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if self._name != value:
            self._name = value
            self.nameChanged.emit()

class ChatCodeModel(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._chat_code = ""

    @Signal
    def chatCodeChanged(self):
        pass

    @Property(str, notify=chatCodeChanged)
    def chatCode(self):
        return self._chat_code

    @chatCode.setter
    def chatCode(self, value):
        if self._chat_code != value:
            self._chat_code = value
            self.chatCodeChanged.emit()

from zeroconf import ServiceBrowser, Zeroconf

class ServiceListener:
    def __init__(self, model):
        self.model = model

    def remove_service(self, zeroconf, type, name):
        self.model.remove_service(name)

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            self.model.add_service(info)

    def update_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            self.model.update_service(name, info)

class DiscoveryModel(QObject):
    servicesChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._services = []
        self.zeroconf = Zeroconf()
        self.listener = ServiceListener(self)
        self.browser = ServiceBrowser(self.zeroconf, "_pychat._tcp.local.", self.listener)

    @Property(list, notify=servicesChanged)
    def services(self):
        return self._services

    def add_service(self, info):
        if not info.parsed_addresses():
            return
        chat_code = info.properties.get(b'chat_code', b'').decode('utf-8')
        service_data = {
            'name': info.name,
            'chat_code': chat_code,
            'address': info.parsed_addresses()[0],
            'port': info.port
        }
        self._services.append(service_data)
        self.servicesChanged.emit()

    def remove_service(self, name):
        self._services = [s for s in self._services if s['name'] != name]
        self.servicesChanged.emit()

    def update_service(self, name, info):
        if not info.parsed_addresses():
            return
        for i, s in enumerate(self._services):
            if s['name'] == name:
                chat_code = info.properties.get(b'chat_code', b'').decode('utf-8')
                self._services[i] = {
                    'name': info.name,
                    'chat_code': chat_code,
                    'address': info.parsed_addresses()[0],
                    'port': info.port
                }
                self.servicesChanged.emit()
                break

    @Slot()
    def refresh(self):
        # Re-browsing can be complex; for now, we just clear and let the listener repopulate
        self._services = []
        self.servicesChanged.emit()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pychat.log')
    ]
)
logger = logging.getLogger('pychat.qt')

class ChatBridge(QObject):
    """Bridge between QML and Python for chat functionality"""
    
    # Signal emitted when a new message is received
    messageReceived = Signal(str, str)  # sender, message
    
    def __init__(self):
        super().__init__()
        self.network_manager = None
        self.is_stopping = False
        self.username = "User"  # Default username
        self.chat_code = "default"  # Default chat code
        
        # Initialize directories
        initialize_directories()
        
    def start_networking(self):
        """Initialize and start the network manager"""
        try:
            self.network_manager = NetworkManager(
                name=self.username,
                chat_code=self.chat_code,
                on_message=self._handle_incoming_message
            )
            self.network_manager.start()
            logger.info(f"Started network manager as {self.username}")
            return True
        except Exception as e:
            logger.error(f"Failed to start network manager: {e}")
            return False
    
    def stop_networking(self):
        """Stop the network manager"""
        if self.is_stopping:
            return
        self.is_stopping = True
        if self.network_manager:
            try:
                self.network_manager.stop()
                logger.info("Stopped network manager")
            except Exception as e:
                logger.error(f"Error stopping network manager: {e}")
    
    def _handle_incoming_message(self, message, sender):
        """Handle an incoming message from the network"""
        try:
            # Emit signal to QML
            self.messageReceived.emit(sender, message)
        except Exception as e:
            logger.error(f"Error handling incoming message: {e}")
    
    @Slot(str)
    def send_message(self, message):
        """Send a message to the chat"""
        if not message.strip():
            return
            
        if not self.network_manager:
            logger.error("Network manager not initialized")
            return
            
        try:
            # In a real implementation, this would use the network manager to send the message
            # For now, we'll just log it
            logger.info(f"Sending message: {message}")
            
            # Emit the message back as a received message (echo for now)
            self.messageReceived.emit(self.username, message)
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    @Slot(str)
    def set_username(self, username):
        """Set the username"""
        if username and username.strip():
            self.username = username.strip()
            logger.info(f"Username set to: {self.username}")
    
    @Slot(str)
    def set_chat_code(self, chat_code):
        """Set the chat code"""
        if chat_code and chat_code.strip():
            self.chat_code = chat_code.strip()
            logger.info(f"Chat code set to: {self.chat_code}")

def main():
    """Main entry point for the Qt application"""
    # Create the application
    app = QApplication(sys.argv)
    
    # Create the chat bridge
    chat_bridge = ChatBridge()

    # Create the name model
    name_model = NameModel()

    # Create the chat code model
    chat_code_model = ChatCodeModel()

    # Create the discovery model
    discovery_model = DiscoveryModel()
    
    # Create the QML application engine
    engine = QQmlApplicationEngine()
    
    # Expose objects to QML
    engine.rootContext().setContextProperty("chatBridge", chat_bridge)
    engine.rootContext().setContextProperty("nameModel", name_model)
    engine.rootContext().setContextProperty("chatCodeModel", chat_code_model)
    engine.rootContext().setContextProperty("discoveryModel", discovery_model)

    qml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Main.qml")
    engine.load(QUrl.fromLocalFile(qml_file))
    
    if not engine.rootObjects():
        logger.error("Failed to load QML file")
        return -1
    
    # Start networking
    if not chat_bridge.start_networking():
        QMessageBox.critical(
            None,
            "Network Error",
            "Failed to initialize network. Please check your connection and try again."
        )
    
    # Set up cleanup on exit
    def cleanup():
        chat_bridge.stop_networking()
    
    # Connect cleanup to application aboutToQuit signal
    app.aboutToQuit.connect(cleanup)
    
    # Start the application event loop
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())

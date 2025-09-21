import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ApplicationWindow {
    id: mainWindow
    visible: true
    width: 800
    height: 600
    title: "PyChat"
    
    // Property to store the chat model
    property var chatModel: ListModel {}
    
    // Connect to the Python backend
    Connections {
        target: chatBridge
        
        function onMessageReceived(sender, message) {
            addReceivedMessage(sender, message);
        }
    }
    
    // Settings dialog
    Dialog {
        id: settingsDialog
        title: "Settings"
        standardButtons: Dialog.Ok | Dialog.Cancel
        modal: true
        
        x: (parent.width - width) / 2
        y: (parent.height - height) / 2
        width: 400
        
        ColumnLayout {
            width: parent ? parent.width : 100
            spacing: 10
            
            Label { text: "Username:" }
            TextField {
                id: usernameField
                Layout.fillWidth: true
                text: "User"
                placeholderText: "Enter your username"
            }
            
            Label { text: "Chat Code:" }
            TextField {
                id: chatCodeField
                Layout.fillWidth: true
                text: "default"
                placeholderText: "Enter chat code"
            }
        }
        
        onAccepted: {
            chatBridge.set_username(usernameField.text);
            chatBridge.set_chat_code(chatCodeField.text);
        }
    }
    
    // Main layout
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        
        // Toolbar
        ToolBar {
            Layout.fillWidth: true
            
            RowLayout {
                anchors.fill: parent
                
                ToolButton {
                    text: qsTr("☰")
                    onClicked: menu.open()
                    
                    Menu {
                        id: menu
                        y: parent.height
                        
                        MenuItem {
                            text: "Settings"
                            onTriggered: settingsDialog.open()
                        }
                        
                        MenuItem {
                            text: "Clear Chat"
                            onTriggered: chatModel.clear()
                        }
                        
                        MenuItem {
                            text: "Exit"
                            onTriggered: Qt.quit()
                        }
                    }
                }
                
                Label {
                    text: "PyChat"
                    elide: Label.ElideRight
                    horizontalAlignment: Qt.AlignHCenter
                    verticalAlignment: Qt.AlignVCenter
                    Layout.fillWidth: true
                    font.bold: true
                }
                
                ToolButton {
                    text: qsTr("⚙️")
                    onClicked: settingsDialog.open()
                }
            }
        }
        
        // Chat messages area
        ScrollView {
            id: scrollView
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 5
            
            ScrollBar.vertical.policy: ScrollBar.AlwaysOn
            
            ListView {
                id: chatView
                model: chatModel
                spacing: 10
                boundsBehavior: Flickable.StopAtBounds
                
                delegate: Rectangle {
                    width: Math.min(chatView.width * 0.8, implicitWidth + 20)
                    height: messageContent.implicitHeight + 20
                    color: isMe ? "#e3f2fd" : "#f5f5f5"
                    radius: 8
                    anchors.right: isMe ? parent.right : undefined
                    anchors.left: isMe ? undefined : parent.left
                    
                    property bool isMe: model.sender === chatBridge.username
                    
                    Column {
                        id: messageContent
                        width: parent.width - 20
                        anchors.centerIn: parent
                        spacing: 5
                        
                        Text {
                            text: model.sender + (isMe ? " (You)" : "")
                            font.bold: true
                            color: isMe ? "#0d47a1" : "#212121"
                            width: parent.width
                            elide: Text.ElideRight
                        }
                        
                        Text {
                            text: model.message
                            width: parent.width
                            wrapMode: Text.WordWrap
                        }
                        
                        Text {
                            text: model.timestamp
                            font.pixelSize: 10
                            color: "#757575"
                            width: parent.width
                            horizontalAlignment: Text.AlignRight
                        }
                    }
                }
                
                onCountChanged: {
                    positionViewAtEnd();
                }
            }
        }
        
        // Message input area
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 100
            color: "#f0f0f0"
            border.color: "#cccccc"
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 5
                spacing: 5
                
                TextArea {
                    id: messageInput
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    placeholderText: "Type your message..."
                    wrapMode: TextEdit.Wrap
                    selectByMouse: true
                    
                    Keys.onReturnPressed: {
                        if (event.modifiers & Qt.ShiftModifier) {
                            // Insert new line
                            insert(cursorPosition, "\n");
                        } else if (text.trim() !== "") {
                            // Send message
                            chatBridge.send_message(text);
                            clear();
                        }
                        event.accepted = true;
                    }
                }
                
                Button {
                    id: sendButton
                    text: "Send"
                    Layout.alignment: Qt.AlignRight
                    enabled: messageInput.text.trim() !== ""
                    
                    onClicked: {
                        if (messageInput.text.trim() !== "") {
                            chatBridge.send_message(messageInput.text);
                            messageInput.clear();
                        }
                    }
                }
            }
        }
    }
    
    // Function to add a received message to the chat
    function addReceivedMessage(sender, message) {
        chatModel.append({
            sender: sender,
            message: message,
            timestamp: new Date().toLocaleTimeString()
        });
    }
    
    // Initialize with default settings
    Component.onCompleted: {
        chatBridge.set_username("User");
        chatBridge.set_chat_code("default");
    }
}
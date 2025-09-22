import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Page {
    Connections {
        target: chatBridge
        function onMessageReceived(sender, message) {
            chatModel.append({ sender: sender, message: message });
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        ListView {
            id: messageView
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: ListModel {
                id: chatModel
            }

            delegate: Rectangle {
                width: parent.width
                height: 40
                color: model.sender === nameModel.name ? "lightblue" : "lightgreen"
                radius: 5

                Text {
                    text: model.sender + ": " + model.message
                    anchors.verticalCenter: parent.verticalCenter
                    leftPadding: 10
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true

            TextField {
                id: messageInput
                Layout.fillWidth: true
                placeholderText: "Type a message..."
            }

            Button {
                id: sendButton
                text: "Send"
                onClicked: {
                    if (messageInput.text.trim() !== "") {
                        busyIndicator.running = true;
                        sendButton.enabled = false;

                        chatBridge.send_message(messageInput.text);
                        messageInput.clear();

                        loaderTimer.start();
                    }
                }
            }
        }
    }

    BusyIndicator {
        id: busyIndicator
        running: false
        anchors.centerIn: parent
    }

    Timer {
        id: loaderTimer
        interval: 500 // 0.5 second
        repeat: false
        onTriggered: {
            busyIndicator.running = false;
            sendButton.enabled = true;
        }
    }
}

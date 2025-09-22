import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: mainWindow
    visible: true
    width: 800
    height: 600
    title: "PyChat"

    SwipeView {
        id: swipeView
        anchors.fill: parent
        interactive: false

        // Page 1: Login
        Page {
            ColumnLayout {
                anchors.centerIn: parent
                spacing: 10

                Label {
                    text: "Enter your name"
                    Layout.alignment: Qt.AlignHCenter
                }
                TextField {
                    id: nameField
                    text: nameModel.name
                    width: 200
                    Layout.alignment: Qt.AlignHCenter
                    placeholderText: "Your name here"
                    onEditingFinished: {
                        nameModel.name = nameField.text
                    }
                }

                Label {
                    text: "Enter your chat code"
                    Layout.alignment: Qt.AlignHCenter
                }
                TextField {
                    id: chatCodeField
                    text: chatCodeModel.chatCode
                    width: 200
                    Layout.alignment: Qt.AlignHCenter
                    placeholderText: "Chat code here"
                    onEditingFinished: {
                        chatCodeModel.chatCode = chatCodeField.text
                    }
                }

                Button {
                    text: "Start Chat"
                    Layout.alignment: Qt.AlignHCenter
                    onClicked: {
                        chatBridge.set_username(nameModel.name);
                        chatBridge.set_chat_code(chatCodeModel.chatCode);
                        swipeView.currentIndex = 1;
                    }
                }
            }
        }

        // Page 2: Discovery
        Loader { source: "discovery.qml" }

        // Page 3: Chat
        Loader { source: "chat.qml" }
    }
}

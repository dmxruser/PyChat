import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Page {
    title: "Discover Users"

    Connections {
        target: discoveryModel
        function onServicesChanged() {
            userListView.model = discoveryModel.services
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        Label {
            text: "Searching for users on the network..."
            Layout.alignment: Qt.AlignHCenter
        }

        ListView {
            id: userListView
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: discoveryModel.services

            delegate: ItemDelegate {
                width: parent.width
                text: modelData.name
                
                onClicked: {
                    console.log("Selected user: " + modelData.name)
                    chatBridge.connect_to_peer(modelData.chat_code)
                    swipeView.currentIndex = 2
                }
            }
        }

        Button {
            text: "Refresh"
            Layout.alignment: Qt.AlignHCenter
            onClicked: {
                discoveryModel.refresh()
            }
        }
    }
}
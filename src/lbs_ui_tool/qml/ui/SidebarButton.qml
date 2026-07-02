// src/lbs_ui_tool/qml/ui/SidebarButton.qml
import QtQuick

Item {
    property bool selected: false
    property string label: ""
    signal clicked()

    width: 172
    height: 44

    Rectangle {
        anchors.fill: parent
        radius: 10
        color: parent.selected ? "#1C1C26" : "transparent"
        border.color: parent.selected ? "#0A84FF" : "transparent"
    }

    Text {
        anchors.centerIn: parent
        text: label
        color: selected ? "#FFFFFF" : "#9A9AA5"
        font.pixelSize: 16
    }

    MouseArea {
        anchors.fill: parent
        onClicked: parent.clicked()
        cursorShape: Qt.PointingHandCursor
    }
}

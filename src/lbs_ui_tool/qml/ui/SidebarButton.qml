// src/lbs_ui_tool/qml/ui/SidebarButton.qml
import QtQuick

Item {
    id: btn
    property bool selected: false
    property string label: ""
    signal clicked()
    width: 172; height: 44

    Rectangle {
        anchors.fill: parent
        radius: 10
        color: btn.selected ? "#1C1C26" : "transparent"
    }
    // 左侧竖条(选中时显示)
    Rectangle {
        visible: btn.selected
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: 3
        height: 20
        radius: 1.5
        color: "#0A84FF"
    }
    Text {
        anchors.left: parent.left
        anchors.leftMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        text: btn.label
        color: btn.selected ? "#FFFFFF" : "#9A9AA5"
        font.pixelSize: 15
        font.bold: btn.selected
    }
    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: btn.clicked()
    }
}

// src/lbs_ui_tool/qml/ui/PageHeader.qml
// 统一页头:标题 + 右侧插槽 + 底部 1px 分割线
import QtQuick

Item {
    id: root
    property string title: ""
    default property alias rightContent: rightSlot.data
    width: parent ? parent.width : 0
    height: 60

    Text {
        anchors.left: parent.left
        anchors.leftMargin: 24
        anchors.verticalCenter: parent.verticalCenter
        text: root.title
        color: "#FFFFFF"
        font.pixelSize: 22
        font.bold: true
    }

    Row {
        id: rightSlot
        anchors.right: parent.right
        anchors.rightMargin: 24
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: "#2E2E3B"
    }
}

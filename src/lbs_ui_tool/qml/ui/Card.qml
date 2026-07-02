// src/lbs_ui_tool/qml/ui/Card.qml
// 圆角卡片容器:统一背景 #1C1C26 + 12 圆角 + 内边距
import QtQuick

Rectangle {
    default property alias content: inner.data
    color: "#1C1C26"
    radius: 12
    border.color: "#2E2E3B"
    border.width: 1

    Item {
        id: inner
        anchors.fill: parent
        anchors.margins: 16
    }
}

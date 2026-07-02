// src/lbs_ui_tool/qml/ui/SensorPage.qml
import QtQuick

Item {
    // Task 17 会使用:仅 NEW-AI 显示传感器更新界面。
    property string productName: ""

    Text {
        text: "传感器更新"
        anchors.centerIn: parent
        color: "#FFFFFF"
        font.pixelSize: 24
    }
}

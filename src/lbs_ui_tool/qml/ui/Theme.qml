// src/lbs_ui_tool/qml/ui/Theme.qml
pragma Singleton
import QtQuick

QtObject {
    readonly property color bg: "#0F0F14"
    readonly property color card: "#1C1C26"
    readonly property color cardHover: "#262633"
    readonly property color accent: "#0A84FF"
    readonly property color text: "#FFFFFF"
    readonly property color textDim: "#9A9AA5"
    readonly property int radius: 18
    readonly property int cardW: 300
    readonly property int cardH: 380
    // 每产品主色(占位,可改)
    readonly property var productColors: ({
        "NEW-AI": "#0A84FF",
        "SPARK-AI": "#FF9F0A",
        "NEXT-AI": "#BF5AF2"
    })
}

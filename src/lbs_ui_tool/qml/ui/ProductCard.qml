// src/lbs_ui_tool/qml/ui/ProductCard.qml
import QtQuick

Rectangle {
    id: card
    property string productName: ""
    property string subtitle: ""
    property color glow: Theme.accent
    width: Theme.cardW
    height: Theme.cardH
    radius: Theme.radius
    color: mouse.containsMouse ? Theme.cardHover : Theme.card
    border.color: glow
    border.width: 1
    // hover 抬升 + 按下缩放
    scale: mouse.pressed ? 0.97 : (mouse.containsMouse ? 1.02 : 1.0)
    Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }

    Column {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        Rectangle {  // 封面占位(渐变 + 首字母)
            width: parent.width
            height: 200
            radius: 14
            gradient: Gradient {
                orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: Qt.lighter(card.glow, 1.2) }
                GradientStop { position: 1.0; color: card.glow }
            }
            Text {
                anchors.centerIn: parent
                text: card.productName.charAt(0)
                font.pixelSize: 96
                font.bold: true
                color: "#FFFFFF66"
            }
        }

        Text {
            text: card.productName
            font.pixelSize: 26
            font.bold: true
            color: Theme.text
        }

        Text {
            text: card.subtitle
            font.pixelSize: 14
            color: Theme.textDim
            width: parent.width
            wrapMode: Text.WordWrap
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: card.clicked()
    }

    signal clicked()
}

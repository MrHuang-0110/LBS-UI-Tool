// src/lbs_ui_tool/qml/ui/HomePage.qml
import QtQuick
import QtQuick.Controls

Item {
    id: home

    Column {
        anchors.centerIn: parent
        spacing: 48

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "选择产品"
            font.pixelSize: 40
            font.bold: true
            color: Theme.text
        }

        Row {
            spacing: 32
            anchors.horizontalCenter: parent.horizontalCenter

            ProductCard {
                productName: "NEW-AI"
                subtitle: "STM32H723 · 支持传感器更新"
                glow: Theme.productColors["NEW-AI"]
                onClicked: home.openWorkspace("NEW-AI")
            }
            ProductCard {
                productName: "SPARK-AI"
                subtitle: "STM32F103"
                glow: Theme.productColors["SPARK-AI"]
                onClicked: home.openWorkspace("SPARK-AI")
            }
            ProductCard {
                productName: "NEXT-AI"
                subtitle: "APM32E103"
                glow: Theme.productColors["NEXT-AI"]
                onClicked: home.openWorkspace("NEXT-AI")
            }
        }
    }

    // HomePage 是独立组件,main.qml 中 ApplicationWindow 的 id(root)在此不可见
    // (QML id 仅在声明所在组件内可见)。通过 ApplicationWindow 附加属性取得宿主
    // 窗口,再调用其 openWorkspace。
    function openWorkspace(productName) {
        ApplicationWindow.window.openWorkspace(productName)
    }
}

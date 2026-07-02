// src/lbs_ui_tool/qml/ui/WorkspacePage.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property string productName: ""
    property var features: ["固件", "监控", "传感器", "Python"]
    property int currentFeature: 0

    Row {
        anchors.fill: parent

        // 左侧功能栏:返回 + 产品名 + 功能按钮
        Column {
            width: 220
            height: parent.height
            spacing: 8
            padding: 24

            Button {
                text: "← 返回"
                flat: true
                // WorkspacePage 根 Item 被 StackView push,通过附加属性
                // StackView.view 取得宿主 StackView 并 pop 回首页。
                onClicked: root.StackView.view.pop()
            }

            Text {
                text: root.productName
                font.pixelSize: 22
                font.bold: true
                color: "#FFFFFF"
                topPadding: 24
            }

            Repeater {
                model: root.features
                SidebarButton {
                    label: modelData
                    selected: index === root.currentFeature
                    // 非 NEW-AI 时禁用"传感器"项(Item.enabled=false 会让 MouseArea 不响应)
                    enabled: !(root.productName !== "NEW-AI" && modelData === "传感器")
                    onClicked: root.currentFeature = index
                }
            }
        }

        // 右侧内容栈
        Rectangle {
            width: parent.width - 220
            height: parent.height
            color: "#0F0F14"

            StackLayout {
                anchors.fill: parent
                currentIndex: root.currentFeature

                FirmwarePage {}
                MonitorPage {}
                SensorPage { productName: root.productName }
                PythonPage {}
            }
        }
    }
}

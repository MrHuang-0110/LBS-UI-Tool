// src/lbs_ui_tool/qml/ui/WorkspacePage.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property string productName: ""
    property var features: ["固件", "监控", "传感器", "Python"]
    property int currentFeature: 0
    // 连接状态由 backend.connected/disconnected 信号驱动;
    // 连接后禁用"连接"按钮、启用"断开",反之亦然。
    property bool isConnected: false

    function refreshPorts() {
        portCombo.model = backend.list_ports()
    }

    Row {
        anchors.fill: parent

        // 左侧功能栏:返回 + 产品名 + 连接区 + 功能按钮
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

            // —— 连接区(收口项 1)——
            // COM 口下拉 + 连接/断开 + 刷新;产品型号由首页选定,只读显示在上方。
            Text {
                text: "连接"
                color: "#9A9AA5"
                font.pixelSize: 12
                topPadding: 16
            }

            ComboBox {
                id: portCombo
                width: 172
                // 无串口时显示占位提示,避免空 ComboBox 令人困惑
                displayText: (currentText === "" ? "无可用串口" : currentText)
            }

            Row {
                spacing: 6
                Button {
                    text: "连接"
                    enabled: !root.isConnected && portCombo.currentText !== ""
                    onClicked: backend.connect_device(portCombo.currentText, root.productName)
                }
                Button {
                    text: "断开"
                    enabled: root.isConnected
                    onClicked: backend.disconnect_device()
                }
            }

            Button {
                text: "刷新端口"
                flat: true
                onClicked: root.refreshPorts()
            }

            Text {
                id: connStatus
                width: 172
                wrapMode: Text.WordWrap
                font.pixelSize: 11
                color: root.isConnected ? "#0A84FF" : "#9A9AA5"
                text: root.isConnected ? "● 已连接" : "○ 未连接"
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

    Component.onCompleted: root.refreshPorts()

    Connections {
        target: backend
        function onConnected() { root.isConnected = true }
        function onDisconnected() { root.isConnected = false }
    }
}

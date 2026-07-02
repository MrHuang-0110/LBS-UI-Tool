// src/lbs_ui_tool/qml/ui/WorkspacePage.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property string productName: ""
    // -1 表示无功能选中(初始或在连接区),0-3 对应 4 个功能页
    property int currentFeature: -1
    // 连接状态由 backend.connected/disconnected 信号驱动;
    // 连接后禁用"连接"按钮、启用"断开",反之亦然。
    property bool isConnected: false
    // 连接失败时由 taskFinished 携带的错误信息,显示在连接状态处。
    property string lastError: ""

    // 功能项元数据,index 与 StackLayout 对应
    property var featureItems: [
        {"key": "firmware", "label": "固件"},
        {"key": "monitor",  "label": "监控"},
        {"key": "sensor",   "label": "传感器"},
        {"key": "python",   "label": "Python"}
    ]

    function refreshPorts() {
        portCombo.model = backend.list_ports()
    }

    Row {
        anchors.fill: parent

        // —— 左侧栏 ——
        Rectangle {
            width: 220
            height: parent.height
            color: "#141420"

            Column {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 8

                // 1. 主页
                SidebarButton {
                    iconSource: icons.home
                    label: "主页"
                    onClicked: root.StackView.view.pop()
                }

                // 2. 产品名
                Text {
                    text: root.productName
                    color: "#FFFFFF"
                    font.pixelSize: 22
                    font.bold: true
                    topPadding: 16
                    bottomPadding: 8
                }

                // 3. 分割线
                Rectangle { width: parent.width; height: 1; color: "#2E2E3B" }

                // 4. 连接区(常驻)
                Row {
                    spacing: 8
                    topPadding: 8
                    Image {
                        source: root.isConnected ? icons.connected : icons.disconnected
                        width: 20; height: 20
                        sourceSize.width: 40; sourceSize.height: 40
                        smooth: true; fillMode: Image.PreserveAspectFit
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: "串口连接"
                        color: "#9A9AA5"
                        font.pixelSize: 12
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                // 端口下拉 + 圆形刷新图标按钮内联一行
                Row {
                    spacing: 6
                    ComboBox {
                        id: portCombo
                        width: 140
                        textRole: "description"   // 显示 "LBS Serial (COM3)"
                        valueRole: "device"       // 提交时用 "COM3"
                        displayText: (currentIndex < 0 || count === 0) ? "无可用串口" : currentText
                    }
                    Button {
                        id: refreshBtn
                        width: 26; height: 26
                        onClicked: root.refreshPorts()
                        ToolTip.text: "刷新端口"
                        ToolTip.visible: hovered
                        ToolTip.delay: 500
                        background: Rectangle {
                            radius: 13
                            color: refreshBtn.hovered ? "#262633" : "#1C1C26"
                            border.color: "#2E2E3B"
                            border.width: 1
                        }
                        contentItem: Text {
                            text: "↻"
                            font.pixelSize: 14
                            color: "#FFFFFF"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }

                Row {
                    spacing: 6
                    Button {
                        text: "连接"
                        enabled: !root.isConnected && portCombo.currentIndex >= 0
                        onClicked: backend.connect_device(portCombo.currentValue, root.productName)
                    }
                    Button {
                        text: "断开"
                        enabled: root.isConnected
                        onClicked: backend.disconnect_device()
                    }
                }

                Text {
                    id: connStatus
                    width: 172
                    wrapMode: Text.WordWrap
                    font.pixelSize: 11
                    color: root.isConnected ? "#0A84FF" : (root.lastError !== "" ? "#FF3B30" : "#9A9AA5")
                    text: root.isConnected ? "● 已连接"
                          : (root.lastError !== "" ? "⚠ " + root.lastError : "○ 未连接")
                }

                // 5. 分割线
                Rectangle {
                    width: parent.width
                    height: 1
                    color: "#2E2E3B"
                    anchors.topMargin: 8
                }

                // 6. 功能项(带图标)
                Repeater {
                    model: root.featureItems
                    SidebarButton {
                        iconSource: icons[modelData.key]
                        label: modelData.label
                        selected: index === root.currentFeature
                        // 非 NEW-AI 时禁用"传感器"项
                        enabled: !(root.productName !== "NEW-AI" && modelData.key === "sensor")
                        onClicked: root.currentFeature = index
                    }
                }
            }
        }

        // —— 右侧内容区 ——
        Rectangle {
            width: parent.width - 220
            height: parent.height
            color: "#0F0F14"

            // currentFeature>=0 时显示对应功能页
            StackLayout {
                anchors.fill: parent
                currentIndex: Math.max(0, root.currentFeature)
                visible: root.currentFeature >= 0
                FirmwarePage {}
                MonitorPage {}
                SensorPage { productName: root.productName }
                PythonPage {}
            }

            // 未选功能时的欢迎屏
            Item {
                anchors.fill: parent
                visible: root.currentFeature < 0
                Column {
                    anchors.centerIn: parent
                    spacing: 12
                    Text {
                        text: root.productName
                        color: "#FFFFFF"
                        font.pixelSize: 32
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        width: parent.width
                    }
                    Text {
                        text: "从左侧选择功能"
                        color: "#9A9AA5"
                        font.pixelSize: 14
                        horizontalAlignment: Text.AlignHCenter
                        width: parent.width
                    }
                }
            }
        }
    }

    Component.onCompleted: root.refreshPorts()

    Connections {
        target: backend
        function onConnected() { root.isConnected = true; root.lastError = "" }
        function onDisconnected() { root.isConnected = false }
        function onTaskFinished(ok, msg) {
            if (!ok && msg.indexOf("连接失败") === 0) root.lastError = msg
        }
    }
}

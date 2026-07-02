// src/lbs_ui_tool/qml/ui/SensorPage.qml
import QtQuick
import QtQuick.Controls

/* 传感器更新页(仅 NEW-AI)。
   NEW-AI 下显示 A~H 8 个端口下拉(默认"保持不动" 0xFF),选完点"更新"
   调 backend.update_sensors(selections) 下发 0x32 帧。
   非 NEW-AI 产品显示"本产品不支持传感器更新"。 */
Item {
    id: root

    property string productName: ""

    // 设备选项:value 用十进制,对应 NewAiProfile.NEW_AI_DEVICE_IDS。
    // 255(0xFF)= 保持不动;其余 9 类为 NEW-AI 支持的传感器/执行器 ID。
    property var deviceOptions: [
        {"label": "保持不动", "value": 255},
        {"label": "大电机",   "value": 161},   // 0xA1
        {"label": "小电机",   "value": 166},   // 0xA6
        {"label": "颜色",     "value": 162},   // 0xA2
        {"label": "超声波",   "value": 163},   // 0xA3
        {"label": "触摸",     "value": 164},   // 0xA4
        {"label": "摄像头",   "value": 167},   // 0xA7
        {"label": "灰度",     "value": 169},   // 0xA9
        {"label": "灰度V2",   "value": 176},   // 0xB0
        {"label": "NFC",      "value": 178}    // 0xB2
    ]

    // 8 端口当前选择(value)。括号包裹对象字面量,避免被解析为语句块。
    // onActivated 只改键值不改引用,点"更新"时直接读当前对象传给 backend。
    property var selections: ({"A": 255, "B": 255, "C": 255, "D": 255,
                               "E": 255, "F": 255, "G": 255, "H": 255})

    Column {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        Text {
            text: "传感器更新"
            color: "#FFFFFF"
            font.pixelSize: 24
            font.bold: true
        }

        Text {
            visible: root.productName !== "NEW-AI"
            text: "本产品不支持传感器更新"
            color: "#9A9AA5"
            font.pixelSize: 16
        }

        Grid {
            visible: root.productName === "NEW-AI"
            columns: 4
            spacing: 12

            Repeater {
                model: ["A", "B", "C", "D", "E", "F", "G", "H"]
                delegate: Column {
                    spacing: 6
                    Text {
                        text: "端口 " + modelData
                        color: "#FFFFFF"
                    }
                    ComboBox {
                        width: 140
                        model: root.deviceOptions
                        textRole: "label"
                        // 默认 currentIndex=0 即"保持不动"(255),与 selections 初值一致。
                        onActivated: root.selections[modelData] = root.deviceOptions[currentIndex].value
                    }
                }
            }
        }

        Button {
            visible: root.productName === "NEW-AI"
            text: "更新"
            onClicked: backend.update_sensors(root.selections)
        }

        Text {
            id: status
            color: "#9A9AA5"
            wrapMode: Text.WordWrap
            width: parent.width
        }
    }

    Connections {
        target: backend
        function onTaskFinished(ok, msg) { status.text = msg }
    }
}

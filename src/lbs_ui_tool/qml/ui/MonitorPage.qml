// src/lbs_ui_tool/qml/ui/MonitorPage.qml
import QtQuick
import QtQuick.Controls

/* 监控页:顶部开关 → 电量/版本/状态三卡 → 端口卡片网格。
   backend.enable_monitor(on) 启动 50ms 串口轮询,解析后经 monitorState 信号
   回推 monitorData,UI 绑定刷新。端口 model 取 Object.keys(monitorData.ports)。 */
Item {
    id: root
    property var monitorData: ({})

    Column {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        Row {
            spacing: 12
            Text {
                text: "监控"
                color: "#FFFFFF"
                font.pixelSize: 24
                font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }
            Switch {
                id: monSwitch
                onToggled: backend.enable_monitor(checked)
            }
        }

        Row {
            spacing: 24

            // 电量
            Rectangle {
                width: 140; height: 70; radius: 12; color: "#1C1C26"
                Column {
                    anchors.centerIn: parent; spacing: 4
                    Text { text: "电量"; color: "#9A9AA5"; font.pixelSize: 12 }
                    Text {
                        text: (root.monitorData.battery !== undefined && root.monitorData.battery !== null)
                              ? (Math.round(root.monitorData.battery) + "%") : "--"
                        color: "#FFFFFF"; font.pixelSize: 20; font.bold: true
                    }
                }
            }

            // 版本
            Rectangle {
                width: 140; height: 70; radius: 12; color: "#1C1C26"
                Column {
                    anchors.centerIn: parent; spacing: 4
                    Text { text: "版本"; color: "#9A9AA5"; font.pixelSize: 12 }
                    Text {
                        text: root.monitorData.version || "--"
                        color: "#FFFFFF"; font.pixelSize: 20; font.bold: true
                    }
                }
            }

            // 状态
            Rectangle {
                width: 140; height: 70; radius: 12; color: "#1C1C26"
                Column {
                    anchors.centerIn: parent; spacing: 4
                    Text { text: "状态"; color: "#9A9AA5"; font.pixelSize: 12 }
                    Text {
                        text: root.monitorData.state || "--"
                        color: "#FFFFFF"; font.pixelSize: 20; font.bold: true
                    }
                }
            }
        }

        // 端口卡片网格
        GridView {
            width: parent.width
            height: 300
            cellWidth: 200
            cellHeight: 120
            model: Object.keys(root.monitorData.ports || {})
            delegate: Rectangle {
                width: 180; height: 100; radius: 12; color: "#1C1C26"
                Column {
                    anchors.centerIn: parent; spacing: 4
                    Text {
                        text: "端口 " + modelData
                        color: "#FFFFFF"; font.bold: true
                    }
                    Text {
                        text: JSON.stringify(root.monitorData.ports[modelData])
                        color: "#9A9AA5"; font.pixelSize: 11
                    }
                }
            }
        }
    }

    Connections {
        target: backend
        function onMonitorState(data) { root.monitorData = data }
    }
}

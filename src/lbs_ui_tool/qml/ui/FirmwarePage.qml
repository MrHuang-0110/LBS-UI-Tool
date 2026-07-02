// src/lbs_ui_tool/qml/ui/FirmwarePage.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

/* 固件下载页:按当前产品的固件包结构渲染每行(分区名 + 只读路径 + 浏览)。
   模板来自 backend.firmware_template() —— 返回 [{partition, required, path}],
   未连接时返回空列表。路径收集用 ListModel 持久化,避开从 Repeater delegate
   外反向读取动态 TextField 的难点。 */
ScrollView {
    id: root
    clip: true

    // 当前正在浏览选文件的行索引,-1 表示无。
    property int _editingIndex: -1

    Column {
        width: 600
        spacing: 16
        padding: 24

        Text {
            text: "固件下载"
            color: "#FFFFFF"
            font.pixelSize: 24
            font.bold: true
        }

        ListModel { id: filesModel }

        Repeater {
            id: repeater
            model: filesModel
            delegate: Row {
                spacing: 12
                Text {
                    width: 120
                    text: (model.partition ? model.partition : "固件")
                          + (model.required ? " *" : "")
                    color: "#9A9AA5"
                    anchors.verticalCenter: parent.verticalCenter
                }
                TextField {
                    width: 320
                    placeholderText: "选择文件..."
                    readOnly: true
                    text: model.path
                    color: "#FFFFFF"
                }
                Button {
                    text: "浏览"
                    onClicked: {
                        root._editingIndex = index
                        fd.open()
                    }
                }
            }
        }

        ProgressBar {
            id: bar
            width: parent.width - 48
            value: 0
        }

        Text {
            id: statusText
            color: "#9A9AA5"
            wrapMode: Text.WordWrap
            width: parent.width - 48
        }

        Button {
            text: "开始更新"
            enabled: filesModel.count > 0
            onClicked: {
                var files = []
                for (var i = 0; i < filesModel.count; i++) {
                    var item = filesModel.get(i)
                    files.push({"partition": item.partition, "path": item.path})
                }
                statusText.text = "更新中..."
                backend.download_firmware(files)
            }
        }
    }

    // 单个 FileDialog 复用:点"浏览"先记录行索引,选完写回 ListModel,
    // delegate 里 TextField.text: model.path 会自动刷新。
    FileDialog {
        id: fd
        onAccepted: {
            var p = currentFile.toString()
            // Windows: file:///C:/... -> C:/... ; Linux: file:///home -> /home
            p = p.replace("file:///", "")
            if (root._editingIndex >= 0)
                filesModel.setProperty(root._editingIndex, "path", p)
        }
    }

    Component.onCompleted: {
        var tpl = backend.firmware_template()
        filesModel.clear()
        for (var i = 0; i < tpl.length; i++) {
            filesModel.append({
                "partition": tpl[i].partition,
                "required": tpl[i].required,
                "path": ""
            })
        }
        if (filesModel.count === 0)
            statusText.text = "未连接,请先连接设备"
    }

    Connections {
        target: backend
        function onProgress(pct, msg) { bar.value = pct / 100; statusText.text = msg }
        function onTaskFinished(ok, msg) { statusText.text = msg }
    }
}

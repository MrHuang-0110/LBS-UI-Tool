// src/lbs_ui_tool/qml/ui/FirmwarePage.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

/* 固件下载页:按当前产品的固件包结构渲染每行(分区名 + 只读路径 + 浏览)。
   模板来自 backend.firmware_template() —— 返回 [{partition, required, path}],
   未连接时返回空列表。路径收集用 ListModel 持久化,避开从 Repeater delegate
   外反向读取动态 TextField 的难点。
   连接前模板为空;连接成功后经 backend.connected 信号重载模板。 */
Item {
    id: root

    // 当前正在浏览选文件的行索引,-1 表示无。
    property int _editingIndex: -1

    // 加载/重载固件模板:清空 ListModel 后按 backend.firmware_template() 重填。
    // 未连接返回 [] 时显示提示;连接后重填并清空提示。
    function loadTemplate() {
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
        else
            statusText.text = ""
    }

    Column {
        anchors.fill: parent
        spacing: 0

        PageHeader { title: "固件下载" }

        ScrollView {
            width: parent.width
            height: parent.height - 60
            clip: true

            Column {
                width: 720
                spacing: 16
                padding: 24

                ListModel { id: filesModel }

                Card {
                    width: parent.width - 48
                    height: filesLayout.height + 32

                    Column {
                        id: filesLayout
                        width: parent.width
                        spacing: 12

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
                    }
                }

                Card {
                    width: parent.width - 48
                    height: 140

                    Column {
                        anchors.fill: parent
                        spacing: 12

                        ProgressBar {
                            id: bar
                            width: parent.width
                            value: 0
                        }

                        Text {
                            id: statusText
                            color: "#9A9AA5"
                            wrapMode: Text.WordWrap
                            width: parent.width
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
                }
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

    Component.onCompleted: root.loadTemplate()

    Connections {
        target: backend
        function onProgress(pct, msg) { bar.value = pct / 100; statusText.text = msg }
        function onTaskFinished(ok, msg) { statusText.text = msg }
        function onConnected() { root.loadTemplate() }
        function onDisconnected() {
            filesModel.clear()
            statusText.text = "未连接,请先连接设备"
        }
    }
}

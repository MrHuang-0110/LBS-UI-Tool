// src/lbs_ui_tool/qml/ui/FirmwarePage.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

/* 固件下载页:选择一个固件包目录,由 backend.scan_firmware_dir() 自动识别分区。
   模板来自 backend.firmware_template() —— 返回 [{partition, required, path}],
   未连接时返回空列表;连接后显示分区骨架(path 全空)。
   选择目录后调 backend.scan_firmware_dir(dir) 重填 filesModel,path 为自动识别到的
   完整文件路径(未识别到 path="")。收集非空 path 项交给 download_firmware。 */
Item {
    id: root

    // 当前选中的固件包目录(纯路径)。
    property string currentDir: ""

    // 已识别分区数,供"开始更新"按钮做响应式 enabled 绑定
    // (直接调用 _identifiedCount() 无法随 ListModel 变化重算)。
    property int identifiedCount: 0

    // 加载/重载固件模板:清空 ListModel 后按 backend.firmware_template() 重填(path 全空)。
    // 未连接返回 [] 时显示提示;连接后重填骨架并提示选择目录。
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
            statusText.text = "请选择固件包目录"
        root.identifiedCount = 0
    }

    // 扫描当前目录:调 backend.scan_firmware_dir() 重填 filesModel。
    function scanCurrentDir() {
        if (!currentDir)
            return
        var res = backend.scan_firmware_dir(currentDir)
        filesModel.clear()
        for (var i = 0; i < res.length; i++)
            filesModel.append({
                "partition": res[i].partition,
                "required": res[i].required,
                "path": res[i].path
            })
        root.identifiedCount = _identifiedCount()
        statusText.text = _identifiedCount() + " / " + filesModel.count + " 个分区已识别"
    }

    // 已识别(path 非空)的分区数。
    function _identifiedCount() {
        var n = 0
        for (var i = 0; i < filesModel.count; i++)
            if (filesModel.get(i).path)
                n++
        return n
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

                // 选择固件包目录区。
                Card {
                    width: parent.width - 48
                    height: 96

                    Column {
                        anchors.fill: parent
                        spacing: 8

                        Row {
                            spacing: 8
                            Button {
                                text: "选择固件包目录"
                                onClicked: folderDialog.open()
                            }
                            Button {
                                text: "重新扫描"
                                enabled: root.currentDir !== ""
                                onClicked: root.scanCurrentDir()
                            }
                        }
                        Text {
                            text: root.currentDir || "未选择目录"
                            color: "#9A9AA5"
                            font.pixelSize: 12
                            elide: Text.ElideMiddle
                            width: parent.width
                        }
                    }
                }

                // 识别结果表:分区名 + 识别状态(✓ 绿 / ○ 灰)+ 文件路径小字。
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
                                Column {
                                    width: 420
                                    anchors.verticalCenter: parent.verticalCenter
                                    Text {
                                        text: model.path
                                              ? "✓ " + model.path.split(/[\/\\]/).pop()
                                              : "○ 未识别"
                                        color: model.path ? "#30D158" : "#9A9AA5"
                                    }
                                    Text {
                                        text: model.path
                                        visible: model.path !== ""
                                        color: "#6A6A75"
                                        font.pixelSize: 11
                                        elide: Text.ElideMiddle
                                        width: parent.width
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
                            enabled: root.identifiedCount > 0
                            onClicked: {
                                var files = []
                                for (var i = 0; i < filesModel.count; i++) {
                                    var item = filesModel.get(i)
                                    if (item.path)
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

    // 选择固件包目录:onAccepted 存目录并自动扫描。
    FolderDialog {
        id: folderDialog
        onAccepted: {
            var p = currentFolder.toString().replace("file:///", "")
            root.currentDir = p
            root.scanCurrentDir()
        }
    }

    Component.onCompleted: root.loadTemplate()

    Connections {
        target: backend
        function onProgress(pct, msg) { bar.value = pct / 100; statusText.text = msg }
        function onTaskFinished(ok, msg) { statusText.text = msg }
        function onConnected() { root.loadTemplate() }
        function onDisconnected() {
            root.currentDir = ""
            filesModel.clear()
            root.identifiedCount = 0
            statusText.text = "未连接,请先连接设备"
        }
    }
}

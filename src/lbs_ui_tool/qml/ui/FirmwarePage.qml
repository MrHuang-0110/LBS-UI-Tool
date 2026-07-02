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
        rebuildPartitions()
        if (filesModel.count === 0)
            statusText.text = "未连接,请先连接设备"
        else
            statusText.text = "请选择固件包目录"
    }

    // 扫描当前目录:调 backend.scan_firmware_dir() 重填 filesModel。
    // scan_firmware_dir 按子目录展开:一个 partition 子目录里 N 个文件 → N 个 FirmwareFile,
    // partition 字段相同;未识别分区有 1 条 path="" 占位。
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
        rebuildPartitions()
        statusText.text = root.identifiedCount + " / " + partitionsModel.count + " 个分区已识别"
    }

    // 从 filesModel 派生 partitionsModel:每个 partition 一个条目。
    // fileCount = 该分区 path 非空的文件数;filesJson = basename 列表的 JSON 字符串。
    // identifiedCount = 至少含 1 个文件的分区数(不是文件总数)。
    function rebuildPartitions() {
        partitionsModel.clear()
        var byPart = {}
        var order = []
        for (var i = 0; i < filesModel.count; i++) {
            var item = filesModel.get(i)
            if (!(item.partition in byPart)) {
                byPart[item.partition] = { required: item.required, files: [] }
                order.push(item.partition)
            }
            if (item.path) {
                var base = item.path.split(/[\/\\]/).pop()
                byPart[item.partition].files.push(base)
            }
        }
        var identified = 0
        for (var j = 0; j < order.length; j++) {
            var name = order[j]
            var g = byPart[name]
            partitionsModel.append({
                "partition": name,
                "required": g.required,
                "fileCount": g.files.length,
                "filesJson": JSON.stringify(g.files),
                "expanded": true
            })
            if (g.files.length > 0)
                identified++
        }
        root.identifiedCount = identified
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

                // 完整文件清单:每个 FirmwareFile 一条(保留 partition/path 对应关系,
                // 供"开始更新"收集)。
                ListModel { id: filesModel }

                // 从 filesModel 派生的分组模型:每个 partition 一条,供分组卡片展示。
                ListModel { id: partitionsModel }

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

                // 识别结果:按 partition 分组的可折叠卡片。每个分区一行,
                // 标题(三角 + 分区名[+*] + 计数),展开时列出该分区所有文件(仅文件名)。
                Card {
                    width: parent.width - 48
                    height: filesLayout.implicitHeight + 32

                    Column {
                        id: filesLayout
                        width: parent.width
                        spacing: 8

                        Repeater {
                            id: repeater
                            model: partitionsModel
                            delegate: Rectangle {
                                // 把外层 delegate 的 model 数据拷到本地属性,
                                // 避免内层 Repeater 的 modelData 与外层 model 混淆。
                                property string partitionName: model.partition
                                property bool partitionRequired: model.required
                                property int partitionFileCount: model.fileCount
                                property bool partitionExpanded: model.expanded
                                property string partitionFilesJson: model.filesJson
                                property int partitionIndex: index

                                width: parent.width
                                height: partitionExpanded
                                        ? (36 + Math.max(1, partitionFileCount) * 22 + 8)
                                        : 36
                                color: "transparent"

                                Column {
                                    anchors.fill: parent
                                    spacing: 0

                                    // 标题行:三角 + 分区名 + 右侧计数/未识别。
                                    Item {
                                        width: parent.width
                                        height: 36

                                        Row {
                                            anchors.left: parent.left
                                            anchors.verticalCenter: parent.verticalCenter
                                            spacing: 8
                                            Text {
                                                text: partitionExpanded ? "▼" : "▶"
                                                color: partitionFileCount > 0 ? "#0A84FF" : "#6A6A75"
                                                font.pixelSize: 12
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                            Text {
                                                text: partitionName + (partitionRequired ? " *" : "")
                                                color: "#FFFFFF"
                                                font.pixelSize: 14
                                                font.bold: true
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                        }
                                        Text {
                                            anchors.right: parent.right
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: partitionFileCount > 0
                                                  ? ("识别 " + partitionFileCount + " 个文件")
                                                  : "未识别"
                                            color: partitionFileCount > 0 ? "#30D158" : "#9A9AA5"
                                            font.pixelSize: 12
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: partitionsModel.setProperty(
                                                           partitionIndex, "expanded", !partitionExpanded)
                                        }
                                    }

                                    // 文件列表(展开时):仅文件名,前置绿色 ✓。
                                    Repeater {
                                        model: partitionExpanded
                                               ? JSON.parse(partitionFilesJson || "[]")
                                               : []
                                        delegate: Text {
                                            x: 20
                                            text: "✓ " + modelData
                                            color: "#30D158"
                                            font.pixelSize: 12
                                            height: 22
                                            verticalAlignment: Text.AlignVCenter
                                        }
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
            partitionsModel.clear()
            root.identifiedCount = 0
            statusText.text = "未连接,请先连接设备"
        }
    }
}

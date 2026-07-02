// src/lbs_ui_tool/qml/ui/PythonPage.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

/* Python 多文件 IDE:左文件树 + 中编辑器 + 右控制台/工具。
   打开项目目录(FolderDialog)→ list_py 列出 .py 文件名 → 点文件
   read_file 填编辑器 → 保存(write_file)/编译(compile_python,调
   rust-msc 生成 .o)/下发(deploy_python,按槽位 0-19)。
   进度与结束经 backend.progress / taskFinished 信号回推到 pyBar + consoleLog。
   路径处理:list_py 只返回文件名,delegate 点击时拼接 currentDir + "/" + filename
   得到完整路径存入 currentFile,后续 read/write/compile/deploy 全用完整路径。
   currentDir 在 FolderDialog onAccepted 里把 QUrl(file:///C:/...)去前缀为 C:/...。 */
Item {
    id: root

    property string currentDir: ""    // 已展开为纯路径(QUrl.toString 去掉 file:///)
    property string currentFile: ""   // 完整路径 = currentDir + "/" + filename
    property string currentOut: ""    // 编译产物 .o 路径
    property var fileModel: []        // .py 文件名列表(不含路径)

    Column {
        anchors.fill: parent
        spacing: 0

        PageHeader { title: "Python 代码" }

        Row {
            width: parent.width
            height: parent.height - 60

            // —— 文件树 ——
            Item {
                id: treePane
                width: 200
                height: parent.height

                Button {
                    id: openBtn
                    text: "打开项目目录"
                    anchors.top: parent.top
                    anchors.topMargin: 12
                    anchors.horizontalCenter: parent.horizontalCenter
                    onClicked: folderDialog.open()
                }

                ListView {
                    id: fileTree
                    anchors.top: openBtn.bottom
                    anchors.topMargin: 8
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 12
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    clip: true
                    model: root.fileModel
                    delegate: Item {
                        width: fileTree.width
                        height: 28
                        Text {
                            text: modelData
                            color: "#FFFFFF"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.currentFile = root.currentDir + "/" + modelData
                                editor.text = backend.read_file(root.currentFile)
                                consoleLog.text = "已加载: " + modelData
                            }
                        }
                    }
                }
            }

            // —— 编辑器 ——
            Rectangle {
                width: parent.width - treePane.width - toolPane.width
                height: parent.height
                color: "#15151C"

                ScrollView {
                    anchors.fill: parent
                    TextArea {
                        id: editor
                        placeholderText: "选择左侧文件以编辑..."
                        font.family: "Consolas"
                        font.pixelSize: 14
                        color: "#FFFFFF"
                        textFormat: TextEdit.PlainText
                        wrapMode: TextEdit.NoWrap
                    }
                }
            }

            // —— 控制台 + 工具 ——
            Column {
                id: toolPane
                width: 300
                height: parent.height
                padding: 12
                spacing: 8

                Row {
                    spacing: 8
                    Text {
                        text: "槽位"
                        color: "#9A9AA5"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    SpinBox {
                        id: slotBox
                        from: 0
                        to: 19
                        value: 0
                    }
                }

                Row {
                    spacing: 8
                    Button {
                        text: "保存"
                        enabled: root.currentFile !== ""
                        onClicked: {
                            backend.write_file(root.currentFile, editor.text)
                            consoleLog.text = "已保存: " + root.currentFile
                        }
                    }
                    Button {
                        text: "编译"
                        enabled: root.currentFile !== ""
                        onClicked: {
                            pyBar.value = 0
                            var o = backend.compile_python(root.currentFile)
                            if (o) {
                                root.currentOut = o
                                consoleLog.text = "已编译: " + o
                            }
                            // 失败时 compile_python 已 emit taskFinished(False, msg),
                            // 由 onTaskFinished 写入错误信息,不在此覆盖以免丢失详情。
                        }
                    }
                    Button {
                        text: "下发"
                        enabled: root.currentOut !== ""
                        onClicked: {
                            pyBar.value = 0
                            backend.deploy_python(root.currentOut, slotBox.value)
                        }
                    }
                }

                TextArea {
                    id: consoleLog
                    width: 276
                    height: 200
                    readOnly: true
                    color: "#9A9AA5"
                    wrapMode: TextEdit.WordWrap
                    text: ""
                }

                ProgressBar {
                    id: pyBar
                    width: 276
                    value: 0
                }
            }
        }
    }

    FolderDialog {
        id: folderDialog
        onAccepted: {
            var p = currentFolder.toString()
            // Windows: file:///C:/... -> C:/... ; Linux: file:///home -> /home
            p = p.replace("file:///", "")
            root.currentDir = p
            root.fileModel = backend.list_py(p)
            consoleLog.text = "已打开目录: " + p
                + " (" + root.fileModel.length + " 个 .py)"
        }
    }

    Connections {
        target: backend
        function onProgress(pct, msg) { pyBar.value = pct / 100; consoleLog.text = msg }
        function onTaskFinished(ok, msg) {
            consoleLog.text = (ok ? "完成: " : "失败: ") + msg
            if (ok) pyBar.value = 1
        }
    }
}

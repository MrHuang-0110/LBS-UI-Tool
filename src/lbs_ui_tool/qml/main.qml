import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "./ui"

ApplicationWindow {
    id: root
    visible: true
    width: 1100; height: 720
    minimumWidth: 900; minimumHeight: 640
    title: "LBS 上位机工具"
    color: "#0F0F14"

    StackView {
        id: stack
        anchors.fill: parent
        initialItem: homePage
    }

    Component { id: homePage; HomePage {} }
    Component { id: workspacePage; WorkspacePage {} }

    function openWorkspace(productName) {
        stack.push(workspacePage, {"productName": productName})
    }
}

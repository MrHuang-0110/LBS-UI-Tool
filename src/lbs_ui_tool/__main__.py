import sys
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine
from lbs_ui_tool.backend import BackendBridge


def _build_icons_dict() -> dict:
    """把 resources/png 下的图标算成 file:/// URL,英文键给 QML 引用。
    自动处理中文文件名的 URL 编码。文件不存在时 URL 仍生成(Image 加载
    静默失败,便于用户后续补齐资源不需改代码)。"""
    # __file__ 是 src/lbs_ui_tool/__main__.py,parent×3 是项目根
    root = Path(__file__).resolve().parent.parent.parent
    png = root / "resources" / "png"
    base = QUrl.fromLocalFile(str(png)).toString()
    mapping = {
        "home":       "主页.png",
        "connected":  "链接.png",
        "disconnected": "链接,断开.png",
        "firmware":   "固件更新.png",
        "monitor":    "监控数据.png",
        "sensor":     "传感器设备.png",
        # 用户已提供代码编辑器图标作为 Python 功能图标
        "python":     "代码编辑器.png",
    }
    # 文件名整体百分号编码(含 ASCII 逗号等分隔符),再拼到目录 URL 之后,
    # 保证含中文/逗号的文件名生成合法且可被 QML Image 加载的 file:/// URL。
    return {
        k: base + "/" + bytes(QUrl.toPercentEncoding(v)).decode()
        for k, v in mapping.items()
    }


def main():
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    backend = BackendBridge()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("icons", _build_icons_dict())
    qml_dir = Path(__file__).parent / "qml"
    engine.addImportPath(str(qml_dir))
    engine.addImportPath(str(qml_dir / "ui"))
    engine.load(str(qml_dir / "main.qml"))
    if not engine.rootObjects():
        sys.exit(-1)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

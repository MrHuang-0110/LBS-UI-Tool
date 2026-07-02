import sys
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from lbs_ui_tool.backend import BackendBridge


def main():
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    backend = BackendBridge()
    engine.rootContext().setContextProperty("backend", backend)
    qml_dir = Path(__file__).parent / "qml"
    engine.addImportPath(str(qml_dir))
    engine.load(qml_dir / "main.qml")
    if not engine.rootObjects():
        sys.exit(-1)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

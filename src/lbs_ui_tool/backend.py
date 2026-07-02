"""暴露给 QML 的应用层单例。

``BackendBridge`` 把产品选择、连接、任务编排与进度信号聚合到一个
``QObject`` 上,由 ``main.py`` 通过 ``setContextProperty`` 注册到 QML
引擎(不使用 ``@QmlElement`` 元注册,以便单元测试时直接实例化)。
"""
from typing import Optional

import serial
from PySide6.QtCore import QObject, Signal, Slot

from lbs_ui_tool.profiles.base import NotSupportedError, ProductProfile
from lbs_ui_tool.profiles.registry import get_profile, list_products
from lbs_ui_tool.protocol.serial_transport import SerialTransport


class BackendBridge(QObject):
    """QML 可调用的应用层桥。"""

    # —— 信号 ——
    progress = Signal(int, str)
    taskFinished = Signal(bool, str)
    monitorState = Signal(dict)
    connected = Signal()
    disconnected = Signal()

    def __init__(self):
        super().__init__()
        self._transport: Optional[SerialTransport] = None
        self._serial = None
        self.profile: Optional[ProductProfile] = None

    @Slot(result="QVariantList")
    def list_products(self):
        return list_products()

    @Slot(result="QVariantList")
    def list_ports(self):
        return SerialTransport.list_ports()

    @property
    def is_connected(self) -> bool:
        return self.profile is not None

    def _open_serial(self, port: str):
        """打开真实串口。可被测试 monkeypatch 替换为 FakeSerial。"""
        return serial.Serial(port, 115200, timeout=0.1)

    @Slot(str, str)
    def connect_device(self, port: str, product: str):
        self._serial = self._open_serial(port)
        self._transport = SerialTransport(self._serial)
        self.profile = get_profile(product, self._transport)
        self.connected.emit()

    @Slot()
    def disconnect_device(self):
        if self._serial:
            self._serial.close()
        self._serial = None
        self._transport = None
        self.profile = None
        self.disconnected.emit()

    @Slot(str, str)
    def emit_progress(self, pct: str, msg: str):
        self.progress.emit(int(pct), msg)

    @Slot(result="QVariantList")
    def firmware_template(self):
        if not self.profile:
            return []
        return [
            {"partition": f.partition, "required": f.required, "path": f.path}
            for f in self.profile.firmware_template().files
        ]

    @Slot(bool)
    def enable_monitor(self, on: bool):
        if self.profile:
            self.profile.enable_monitor(on)

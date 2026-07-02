"""暴露给 QML 的应用层单例。

``BackendBridge`` 把产品选择、连接、任务编排与进度信号聚合到一个
``QObject`` 上,由 ``main.py`` 通过 ``setContextProperty`` 注册到 QML
引擎(不使用 ``@QmlElement`` 元注册,以便单元测试时直接实例化)。
"""
from typing import Optional

import serial
from PySide6.QtCore import QObject, QTimer, Signal, Slot

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
        self._monitor_timer = QTimer(self)
        self._monitor_timer.timeout.connect(self._poll_serial)
        self._buf = b""

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

    @Slot("QVariantList")
    def download_firmware(self, files):
        """files: [{"partition":..., "path":...}] 由 QML 收集。

        同步执行(阻塞调用线程);真机固件下发耗时较长会卡 UI 线程,
        本任务先简单同步实现,后续可优化为 worker 线程(不在本任务范围)。
        """
        from lbs_ui_tool.profiles.base import FirmwarePackage, FirmwareFile
        if not self.profile:
            self.taskFinished.emit(False, "未连接")
            return
        pkg = FirmwarePackage(
            files=[FirmwareFile(f["partition"], f["path"]) for f in files if f.get("path")]
        )
        try:
            self.profile.download_firmware(pkg, lambda p, m: self.progress.emit(p, m))
            self.taskFinished.emit(True, "固件更新完成")
        except Exception as e:
            self.taskFinished.emit(False, str(e))

    @Slot("QVariantMap")
    def update_sensors(self, ports_map):
        """ports_map: {"A":161, "H":166, ...} 由 QML 传感器页收集。

        NEW-AI profile 的 update_sensors 只 write 0x32 帧不读 ACK,
        故无需向 FakeSerial 灌响应。
        """
        if not self.profile:
            self.taskFinished.emit(False, "未连接")
            return
        try:
            self.profile.update_sensors({k: int(v) for k, v in ports_map.items()})
            self.taskFinished.emit(True, "传感器更新指令已发送")
        except NotSupportedError as e:
            self.taskFinished.emit(False, str(e))
        except Exception as e:
            self.taskFinished.emit(False, str(e))

    @Slot(bool)
    def enable_monitor(self, on: bool):
        if self.profile:
            self.profile.enable_monitor(on)
            if on:
                self._monitor_timer.start(50)
            else:
                self._monitor_timer.stop()

    def _poll_serial(self):
        from lbs_ui_tool.protocol.frame_codec import FrameCodec
        if not self._transport:
            return
        self._buf += self._transport.read_once()
        frames, self._buf = FrameCodec.decode_stream(self._buf)
        for f in frames:
            try:
                st = self.profile.parse_monitor(f.data)
                self.monitorState.emit(self._state_to_dict(st))
            except Exception:
                pass

    @staticmethod
    def _state_to_dict(st):
        return {"battery": st.battery, "version": st.version,
                "state": st.state, "ports": {str(k): v for k, v in st.ports.items()}}

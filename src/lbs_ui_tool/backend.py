"""暴露给 QML 的应用层单例。

``BackendBridge`` 把产品选择、连接、任务编排与进度信号聚合到一个
``QObject`` 上,由 ``main.py`` 通过 ``setContextProperty`` 注册到 QML
引擎(不使用 ``@QmlElement`` 元注册,以便单元测试时直接实例化)。
"""
import threading
from typing import Callable, Optional

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
        try:
            self._serial = self._open_serial(port)
        except Exception as e:
            self._serial = None
            self._transport = None
            self.profile = None
            self.taskFinished.emit(False, f"连接失败: {e}")
            return
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

    def _run_in_worker(self, fn: Callable[[], None]) -> None:
        """在后台守护线程执行 fn;fn 内部 emit 的 Qt 信号经 QueuedConnection
        自动回主线程事件循环,UI 不卡顿。fn 抛异常时统一 emit
        taskFinished(False, 错误信息)。

        Qt 信号是线程安全的:BackendBridge 是 main thread 的 QObject,
        从 worker 线程调用 ``signal.emit(...)`` 时,默认 AutoConnection
        退化为 QueuedConnection,把发射投递到主线程事件循环。
        """
        def worker():
            try:
                fn()
            except Exception as e:  # noqa: BLE001 —— worker 边界统一兜底
                self.taskFinished.emit(False, str(e))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

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

        在 worker 线程执行,避免真机固件下发耗时卡 UI。启动前停掉监控
        轮询定时器,确保 worker 独占串口(协议语义:OTA 时监控应关)。
        完成后不自动重启监控——由 UI 重新打开监控开关恢复。
        """
        from lbs_ui_tool.profiles.base import FirmwarePackage, FirmwareFile
        if not self.profile:
            self.taskFinished.emit(False, "未连接")
            return
        pkg = FirmwarePackage(
            files=[FirmwareFile(f["partition"], f["path"]) for f in files if f.get("path")]
        )
        self._monitor_timer.stop()

        def task():
            self.profile.download_firmware(pkg, lambda p, m: self.progress.emit(p, m))
            self.taskFinished.emit(True, "固件更新完成")

        self._run_in_worker(task)

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
        if not self.profile:
            self.taskFinished.emit(False, "未连接,请先连接设备")
            return
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

    # —— Python IDE 相关槽(Task 18)——

    @Slot(str, result=str)
    def compile_python(self, src_path):
        """调用 PikaCompiler 把 .py 编译为 .o。成功返回 out 路径,
        失败 emit taskFinished(False, 错误信息)并返回空串。"""
        from lbs_ui_tool.pika_compiler import PikaCompiler
        try:
            out = PikaCompiler().compile(src_path)
            return out
        except Exception as e:
            self.taskFinished.emit(False, str(e))
            return ""

    @Slot(str, int)
    def deploy_python(self, o_path, slot):
        """把 .o 字节码下发到指定槽位(0-19)。在 worker 线程执行,
        避免下发耗时卡 UI;启动前停监控定时器以独占串口。"""
        if not self.profile:
            self.taskFinished.emit(False, "未连接")
            return
        self._monitor_timer.stop()

        def task():
            self.profile.deploy_python(o_path, slot, lambda p, m: self.progress.emit(p, m))
            self.taskFinished.emit(True, "下发完成")

        self._run_in_worker(task)

    @Slot(str, result=str)
    def read_file(self, path):
        """读取 UTF-8 文本文件全文,供编辑器加载。"""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    @Slot(str, str)
    def write_file(self, path, content):
        """把编辑器内容写回文件(保存)。"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    @Slot(str, result="QVariantList")
    def list_py(self, folder):
        """列出 folder 目录下所有 .py 文件名(不含子目录)。
        folder 可能为 QUrl(QML 传入)或纯路径字符串。"""
        import os
        if hasattr(folder, "toString"):
            folder = folder.toString()
        folder = str(folder).replace("file:///", "")
        return [f for f in os.listdir(folder) if f.endswith(".py")]

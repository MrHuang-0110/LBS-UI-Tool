"""SPARK-AI 适配器: 自定义帧 app+version 升级,不支持传感器更新。

固件包 app+version,统一用 0xDA 建文件,文件名按分区取自 PARTITION_FILENAMES
(app.bin / version.txt),写内部 Flash 0x08010000 + SPI Flash FATFS。
Python 字节码: 0xB6 进入 -> 0xDA 建文件 ``<slot>.o`` -> 0xB9 退出。
监控 JSON 归一化,电量从 adc.bat 用正则提取数字(如 "85%"->85.0),状态取 WillAiState。
"""
import json
import re
from typing import Callable, Optional

from lbs_ui_tool.profiles.base import (
    FirmwareFile,
    FirmwarePackage,
    MonitorState,
    ProductProfile,
)
from lbs_ui_tool.protocol.frame_codec import FrameCodec
from lbs_ui_tool.protocol.frame_file_transfer import FrameFileTransfer
from lbs_ui_tool.protocol.serial_transport import SerialTransport

CMD_PY_ENTER = 0xB6
CMD_PY_EXIT = 0xB9
CMD_MONITOR_ON = 0xBA
CMD_MONITOR_OFF = 0xBE

# SPARK 统一用 0xDA 建文件,以文件名区分分区(写不同 Flash 区)。
PARTITION_FILENAMES = {"app": "app.bin", "version": "version.txt"}


class SparkAiProfile(ProductProfile):
    name = "SPARK-AI"
    supports_sensor_update = False

    def __init__(self, transport: SerialTransport):
        self._t = transport
        self._fft = FrameFileTransfer(transport)

    def handshake(self) -> bool:
        # SPARK-AI 无显式握手帧,连接即就绪。
        return True

    def firmware_template(self) -> FirmwarePackage:
        return FirmwarePackage(files=[
            FirmwareFile("app", "", required=True),
            FirmwareFile("version", "", required=False),
        ])

    def download_firmware(self, package: FirmwarePackage,
                          progress_cb: Optional[Callable[[int, str], None]]) -> None:
        files = [f for f in package.files if f.path]
        total = len(files)
        for i, f in enumerate(files):
            name = PARTITION_FILENAMES.get(f.partition, f.partition)
            with open(f.path, "rb") as fh:
                data = fh.read()

            def cb(pct: int, _partition: str = f.partition, _i: int = i):
                if progress_cb:
                    progress_cb(int((_i + pct / 100) * 100 / total), f"{_partition} {pct}%")

            ok = self._fft.send(0xDA, name, data, progress_cb=cb)
            if not ok:
                raise RuntimeError(f"{f.partition} 下发失败")

    def deploy_python(self, o_path: str, slot: int,
                      progress_cb: Optional[Callable[[int, str], None]]) -> None:
        self._t.write(bytes(FrameCodec.encode(CMD_PY_ENTER, b"")))
        with open(o_path, "rb") as fh:
            data = fh.read()
        cb = progress_cb and (lambda p: progress_cb(p, "下发"))
        ok = self._fft.send(0xDA, f"{slot}.o", data, progress_cb=cb)
        self._t.write(bytes(FrameCodec.encode(CMD_PY_EXIT, b"")))
        if not ok:
            raise RuntimeError("Python 字节码下发失败")

    def enable_monitor(self, on: bool) -> None:
        cmd = CMD_MONITOR_ON if on else CMD_MONITOR_OFF
        self._t.write(bytes(FrameCodec.encode(cmd, b"")))

    def parse_monitor(self, raw: bytes) -> MonitorState:
        obj = json.loads(raw)
        state = MonitorState()
        for d in obj.get("deviceList", []):
            port = d.get("port")
            state.ports[port] = {k: v for k, v in d.items() if k != "port"}
        adc = obj.get("adc", {})
        if "bat" in adc:
            m = re.search(r"\d+", str(adc["bat"]))
            if m:
                state.battery = float(m.group())
        if "version" in obj:
            state.version = str(obj["version"])
        if "heap" in obj:
            state.heap = str(obj["heap"])
        state.state = obj.get("WillAiState")
        return state

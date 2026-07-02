"""NEXT-AI 适配器: YMODEM 单 bin 升级,不支持传感器更新。

固件单 .bin 与 Python 字节码均走 YMODEM(单文件),监控 JSON 归一化,
电量 bat 转 float(解析失败容忍),version 转 str,state 取 ``state`` 或
``NextAiState``。传感器更新不实现,继承基类抛 NotSupportedError。
"""
import json
from typing import Callable, Optional

from lbs_ui_tool.profiles.base import (
    FirmwareFile,
    FirmwarePackage,
    MonitorState,
    ProductProfile,
)
from lbs_ui_tool.protocol.frame_codec import FrameCodec
from lbs_ui_tool.protocol.serial_transport import SerialTransport
from lbs_ui_tool.protocol.ymodem import YmodemTransfer

CMD_MONITOR_ON = 0xBA
CMD_MONITOR_OFF = 0xBE


class NextAiProfile(ProductProfile):
    name = "NEXT-AI"
    supports_sensor_update = False

    def __init__(self, transport: SerialTransport, block_size: int = 1024):
        self._t = transport
        self._block_size = block_size
        self._ymodem = YmodemTransfer(transport, block_size=block_size)

    def handshake(self) -> bool:
        # NEXT-AI 无显式握手帧,连接即就绪。
        return True

    def firmware_template(self) -> FirmwarePackage:
        # 单 bin: 无分区概念,partition 留空。
        return FirmwarePackage(files=[FirmwareFile("", "", required=True)])

    def scan_firmware_dir(self, folder: str) -> FirmwarePackage:
        """NEXT-AI 目录里放一个 .bin(任意文件名),取字典序第一个 .bin。"""
        import os
        try:
            bins = sorted(f for f in os.listdir(folder) if f.endswith(".bin"))
        except OSError:
            bins = []
        path = os.path.join(folder, bins[0]) if bins else ""
        return FirmwarePackage(files=[FirmwareFile(partition="", path=path, required=True)])

    def download_firmware(self, package: FirmwarePackage,
                          progress_cb: Optional[Callable[[int, str], None]]) -> None:
        f = next(x for x in package.files if x.path)
        with open(f.path, "rb") as fh:
            data = fh.read()
        ok = self._ymodem.send(
            "firmware.bin", data,
            progress_cb=progress_cb and (lambda s, t: progress_cb(int(s * 100 / t), "下发")),
        )
        if not ok:
            raise RuntimeError("YMODEM 固件下发失败")

    def deploy_python(self, o_path: str, slot: int,
                      progress_cb: Optional[Callable[[int, str], None]]) -> None:
        with open(o_path, "rb") as fh:
            data = fh.read()
        ok = self._ymodem.send(
            f"{slot}.o", data,
            progress_cb=progress_cb and (lambda s, t: progress_cb(int(s * 100 / t), "下发")),
        )
        if not ok:
            raise RuntimeError("YMODEM Python 下发失败")

    def enable_monitor(self, on: bool) -> None:
        self._t.write(bytes(FrameCodec.encode(CMD_MONITOR_ON if on else CMD_MONITOR_OFF, b"")))

    def parse_monitor(self, raw: bytes) -> MonitorState:
        obj = json.loads(raw)
        state = MonitorState()
        for d in obj.get("deviceList", []):
            port = d.get("port")
            state.ports[port] = {k: v for k, v in d.items() if k != "port"}
        if "bat" in obj:
            try:
                state.battery = float(obj["bat"])
            except (TypeError, ValueError):
                pass
        if "version" in obj:
            state.version = str(obj["version"])
        state.state = obj.get("state") or obj.get("NextAiState")
        return state

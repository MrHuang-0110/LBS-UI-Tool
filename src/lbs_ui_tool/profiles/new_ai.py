"""NEW-AI 适配器: 自定义帧分区升级 + 传感器更新(0x32) + 9 类设备 ID。

固件用分区命令码(0xDA app / 0xDB boot / 0xDC config / 0xDD version / 0xEC music),
Python 字节码用 0xDA 建文件到 ``<slot>.o``,监控 JSON 归一化,传感器更新发 0x32 帧。
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
from lbs_ui_tool.protocol.frame_file_transfer import FrameFileTransfer
from lbs_ui_tool.protocol.serial_transport import SerialTransport

# 源码核实: motor.h / color.h / ultrasion.h / touch.h / camer.h / gray.h / grayv2.h / nfc_car.h
NEW_AI_DEVICE_IDS = {
    "big_motor": 0xA1,
    "small_motor": 0xA6,   # 源码原名 DEV_ID_SMALL_Motor
    "color": 0xA2,
    "ultrasonic": 0xA3,
    "touch": 0xA4,
    "camera": 0xA7,
    "gray": 0xA9,
    "gray_v2": 0xB0,
    "nfc": 0xB2,
}

# 分区命令码: piKaNewAI-Boot2/Core/Inc/main.h:66-71
PARTITION_CMDS = {
    "app": 0xDA,
    "boot": 0xDB,
    "config": 0xDC,
    "version": 0xDD,
    "music": 0xEC,
}

CMD_PY_ENTER = 0xB6
CMD_PY_EXIT = 0xB9
CMD_MONITOR_ON = 0xBA
CMD_MONITOR_OFF = 0xBE
CMD_SENSOR_UPDATE = 0x32
CMD_ENTER_BOOTLOADER = 0x6F
BOOTLOADER_MAGIC = b"RESET_FWLIB"
KEEP = 0xFF
N_PORTS = 8


class NewAiProfile(ProductProfile):
    name = "NEW-AI"
    supports_sensor_update = True

    def __init__(self, transport: SerialTransport):
        self._t = transport
        self._fft = FrameFileTransfer(transport)

    def handshake(self) -> bool:
        # NEW-AI 无显式握手帧,连接即就绪。
        return True

    def needs_bootloader_switch(self) -> bool:
        return True

    def enter_bootloader(self) -> None:
        """发 0x6F + "RESET_FWLIB" 让 APP 复位到 BOOT。不等 ACK,设备立即重启。"""
        self._t.write(bytes(FrameCodec.encode(CMD_ENTER_BOOTLOADER, BOOTLOADER_MAGIC)))

    def firmware_template(self) -> FirmwarePackage:
        return FirmwarePackage(files=[
            FirmwareFile("app", "", required=True),
            FirmwareFile("boot", "", required=False),
            FirmwareFile("config", "", required=False),
            FirmwareFile("music", "", required=False),
            FirmwareFile("version", "", required=False),
        ])

    def download_firmware(self, package: FirmwarePackage,
                          progress_cb: Optional[Callable[[int, str], None]]) -> None:
        files = [f for f in package.files if f.path]
        total = len(files)
        for i, f in enumerate(files):
            cmd = PARTITION_CMDS[f.partition]
            with open(f.path, "rb") as fh:
                data = fh.read()

            def cb(pct: int, _partition: str = f.partition, _i: int = i):
                if progress_cb:
                    progress_cb(int((_i + pct / 100) * 100 / total), f"{_partition} {pct}%")

            ok = self._fft.send(cmd, f.partition, data, block_size=128, progress_cb=cb)
            if not ok:
                raise RuntimeError(f"{f.partition} 下发失败")

    def deploy_python(self, o_path: str, slot: int,
                      progress_cb: Optional[Callable[[int, str], None]]) -> None:
        self._t.write(bytes(FrameCodec.encode(CMD_PY_ENTER, b"")))
        with open(o_path, "rb") as fh:
            data = fh.read()
        name = f"{slot}.o"
        cb = progress_cb and (lambda p: progress_cb(p, "下发"))
        ok = self._fft.send(0xDA, name, data, block_size=128, progress_cb=cb)
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
            entry = {k: v for k, v in d.items() if k != "port"}
            state.ports[port] = entry
        if "bat" in obj:
            state.battery = float(obj["bat"])
        if "version" in obj:
            state.version = str(obj["version"])
        if "heap" in obj:
            state.heap = str(obj["heap"])
        state.state = obj.get("NewAiState")
        return state

    def update_sensors(self, ports: dict[str, int]) -> None:
        data = bytearray([KEEP] * N_PORTS)
        for label, dev_id in ports.items():
            idx = ord(label.upper()) - ord("A")
            if 0 <= idx < N_PORTS:
                data[idx] = dev_id
        self._t.write(bytes(FrameCodec.encode(CMD_SENSOR_UPDATE, bytes(data))))

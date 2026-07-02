# src/lbs_ui_tool/profiles/base.py
"""产品适配器抽象层。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional


class NotSupportedError(Exception):
    """产品不支持该功能。"""


@dataclass
class FirmwareFile:
    partition: str
    path: str
    required: bool = True


@dataclass
class FirmwarePackage:
    files: list[FirmwareFile]


@dataclass
class MonitorState:
    """归一化监控状态,UI 只认这个。"""
    ports: dict[int, dict] = field(default_factory=dict)   # port -> {type, values}
    battery: Optional[float] = None
    version: Optional[str] = None
    heap: Optional[str] = None
    state: Optional[str] = None
    extra: dict = field(default_factory=dict)


class ProductProfile(ABC):
    name: str
    supports_sensor_update: bool = False

    @abstractmethod
    def handshake(self) -> bool: ...

    @abstractmethod
    def firmware_template(self) -> FirmwarePackage: ...

    @abstractmethod
    def download_firmware(self, package: FirmwarePackage,
                          progress_cb: Optional[Callable[[int, str], None]]) -> None: ...

    @abstractmethod
    def deploy_python(self, o_path: str, slot: int,
                      progress_cb: Optional[Callable[[int, str], None]]) -> None: ...

    @abstractmethod
    def enable_monitor(self, on: bool) -> None: ...

    @abstractmethod
    def parse_monitor(self, raw: bytes) -> MonitorState: ...

    def scan_firmware_dir(self, folder: str) -> FirmwarePackage:
        """扫描目录,按 firmware_template() 的分区顺序寻找匹配文件,
        返回填好 path 的 FirmwarePackage。找不到的分区 path 保持空串。
        默认实现按 partition 名(如 "app")在 folder 里找同名无后缀文件。
        子类可覆盖以实现自定义规则(如 NEXT-AI 找 .bin)。"""
        import os
        tpl = self.firmware_template()
        result_files = []
        try:
            entries = set(os.listdir(folder))
        except OSError:
            entries = set()
        for f in tpl.files:
            matched_path = ""
            if f.partition and f.partition in entries:
                candidate = os.path.join(folder, f.partition)
                if os.path.isfile(candidate):
                    matched_path = candidate
            result_files.append(FirmwareFile(partition=f.partition, path=matched_path, required=f.required))
        return FirmwarePackage(files=result_files)

    def update_sensors(self, ports: dict[str, int]) -> None:
        raise NotSupportedError(f"{self.name} 不支持传感器更新")

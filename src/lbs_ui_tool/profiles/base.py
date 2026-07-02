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

    def update_sensors(self, ports: dict[str, int]) -> None:
        raise NotSupportedError(f"{self.name} 不支持传感器更新")

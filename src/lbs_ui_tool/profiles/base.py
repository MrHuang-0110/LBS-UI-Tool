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
        """扫描目录,按 firmware_template() 的分区顺序寻找匹配。

        默认实现:每个分区是 folder 下同名子目录,里面所有文件都要下发,
        共用同一分区命令码。子目录里 N 个文件展开成 N 个 FirmwareFile,
        partition 字段共享(profile.download_firmware 循环遍历即天然按
        partition 发对应命令码 + 文件)。

        兼容旧假设(partition 名直接是文件):若 folder/partition 是文件
        而非目录,保留为单个 FirmwareFile。

        找不到的分区(子目录不存在或空)保留一条 path="" 占位。
        子类可覆盖以实现自定义规则(如 NEXT-AI 找 .bin)。"""
        import os
        tpl = self.firmware_template()
        result_files: list[FirmwareFile] = []
        for f in tpl.files:
            if not f.partition:
                # 空 partition:走子类逻辑或占位
                result_files.append(FirmwareFile(partition="", path="", required=f.required))
                continue
            target = os.path.join(folder, f.partition)
            if os.path.isdir(target):
                try:
                    names = sorted(n for n in os.listdir(target)
                                   if os.path.isfile(os.path.join(target, n)))
                except OSError:
                    names = []
                if not names:
                    result_files.append(FirmwareFile(partition=f.partition, path="", required=f.required))
                else:
                    for n in names:
                        result_files.append(FirmwareFile(
                            partition=f.partition,
                            path=os.path.join(target, n),
                            required=f.required,
                        ))
            elif os.path.isfile(target):
                result_files.append(FirmwareFile(partition=f.partition, path=target, required=f.required))
            else:
                result_files.append(FirmwareFile(partition=f.partition, path="", required=f.required))
        return FirmwarePackage(files=result_files)

    def update_sensors(self, ports: dict[str, int]) -> None:
        raise NotSupportedError(f"{self.name} 不支持传感器更新")

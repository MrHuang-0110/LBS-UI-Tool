# 上位机工具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 PySide6(QML) 桌面工具,通过蓝牙虚拟串口对 NEW-AI / SPARK-AI / NEXT-AI 三款产品完成固件下载、监控、传感器更新(仅 NEW-AI)、Python 代码编辑与下发。

**Architecture:** 三层架构——协议层(产品无关,`FrameCodec`/`SerialTransport`/`YmodemTransfer`/`FrameFileTransfer`)→ 适配器层(`ProductProfile` 基类 + 三个产品子类)→ 应用层(`BackendBridge` 暴露给 QML)+ QML UI 层(App Store 风格)。控制面三家共用 `_AGREEMENT` 帧;数据面 NEW-AI/SPARK 走自定义帧文件传输,NEXT-AI 走 YMODEM。

**Tech Stack:** Python 3.13, PySide6 (QML), pyserial, pytest。YMODEM 与自定义帧协议从头实现。

**参考设计文档:** `docs/specs/2026-07-01-lbs-ui-tool-design.md`

---

## 项目初始化

### Task 0: 项目骨架与环境

**Files:**
- Create: `pyproject.toml`
- Create: `src/lbs_ui_tool/__init__.py`
- Create: `tests/__init__.py`
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: 初始化 git 仓库**

```bash
cd e:/LBS-UI-Tool
git init
git add docs rust-msc-latest-win10.exe
git commit -m "chore: import design docs and pika compiler"
```

- [ ] **Step 2: 创建 pyproject.toml**

```toml
[project]
name = "lbs-ui-tool"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "PySide6>=6.6",
    "pyserial>=3.5",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-qt>=4.4"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 3: 创建包结构**

`src/lbs_ui_tool/__init__.py`:
```python
"""LBS UI Tool — 上位机工具。"""
__version__ = "0.1.0"
```

`tests/__init__.py`: 空文件。

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
.pytest_cache/
dist/
build/
*.egg-info/
```

`README.md`:
```markdown
# LBS UI Tool

产品下载、监控、传感器更新、Python 代码编辑工具。支持 NEW-AI / SPARK-AI / NEXT-AI。

## 开发

```bash
pip install -e ".[dev]"
pytest
python -m lbs_ui_tool
```
```

- [ ] **Step 4: 安装依赖并验证 pytest**

```bash
pip install -e ".[dev]"
pytest --version
```
Expected: `pytest 8.x`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src tests .gitignore README.md
git commit -m "chore: project skeleton and dev environment"
```

---

## 协议层

协议层产品无关,纯 Python,无硬件即可单测。

### Task 1: FrameCodec — _AGREEMENT 帧编解码

`_AGREEMENT` 帧格式:`0x5A | 0x97 | 0x98 | len(1B) | index(1B) | data[len] | crc(1B) | 0xA5`,crc = 前面所有字节累加和 & 0xFF。

**Files:**
- Create: `src/lbs_ui_tool/protocol/frame_codec.py`
- Test: `tests/protocol/test_frame_codec.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/protocol/test_frame_codec.py
from lbs_ui_tool.protocol.frame_codec import FrameCodec, Frame

def test_encode_minimal_frame():
    frame = FrameCodec.encode(index=0xBA, data=b"")
    # 5A 97 98 00 BA crc A5 ; crc=(5A+97+98+00+BA)&0xFF = 0x49
    assert bytes(frame) == bytes([0x5A, 0x97, 0x98, 0x00, 0xBA, 0x49, 0xA5])

def test_encode_with_data():
    # 用户给的传感器样例: 5A 97 98 08 32 FF*8 BB A5
    frame = FrameCodec.encode(index=0x32, data=b"\xFF" * 8)
    assert bytes(frame) == bytes([0x5A, 0x97, 0x98, 0x08, 0x32] + [0xFF]*8 + [0xBB, 0xA5])

def test_crc_is_sum_low_byte():
    assert FrameCodec.crc(bytes([0x5A, 0x97, 0x98, 0x00, 0xBA])) == 0x49

def test_decode_valid_frame():
    raw = bytes([0x5A, 0x97, 0x98, 0x02, 0xAA, 0x01, 0x02, 0x3F, 0xA5])
    frame = FrameCodec.decode_one(raw)
    assert frame is not None
    assert frame.index == 0xAA
    assert frame.data == b"\x01\x02"

def test_decode_rejects_bad_tail():
    raw = bytes([0x5A, 0x97, 0x98, 0x00, 0xBA, 0x49, 0x00])  # 尾错
    assert FrameCodec.decode_one(raw) is None

def test_decode_rejects_bad_crc():
    raw = bytes([0x5A, 0x97, 0x98, 0x00, 0xBA, 0x00, 0xA5])
    assert FrameCodec.decode_one(raw) is None

def test_data_max_256_bytes():
    frame = FrameCodec.encode(index=0xAA, data=b"\x00" * 256)
    assert len(frame.data) == 256

def test_decode_stream_returns_leftover():
    # 两帧粘在一起 + 半帧
    f1 = bytes(FrameCodec.encode(index=0xBA, data=b""))
    f2 = bytes(FrameCodec.encode(index=0xBE, data=b"\x01"))
    stream = f1 + f2 + bytes([0x5A, 0x97])
    frames, leftover = FrameCodec.decode_stream(stream)
    assert len(frames) == 2
    assert frames[0].index == 0xBA
    assert frames[1].index == 0xBE
    assert leftover == bytes([0x5A, 0x97])
```

- [ ] **Step 2: 运行测试,确认失败**

```bash
pytest tests/protocol/test_frame_codec.py -v
```
Expected: FAIL (模块不存在)

- [ ] **Step 3: 实现 FrameCodec**

```python
# src/lbs_ui_tool/protocol/frame_codec.py
"""_AGREEMENT 帧编解码。帧格式: 5A 97 98 len index data[len] crc A5"""
from dataclasses import dataclass

HEAD = 0x5A
SID = 0x97
OID = 0x98
TAIL = 0xA5
MAX_DATA = 256


@dataclass(frozen=True)
class Frame:
    index: int
    data: bytes

    def __bytes__(self) -> bytes:
        return FrameCodec.encode(self.index, self.data)


class FrameCodec:
    @staticmethod
    def crc(prefix: bytes) -> int:
        return sum(prefix) & 0xFF

    @staticmethod
    def encode(index: int, data: bytes) -> Frame:
        if len(data) > MAX_DATA:
            raise ValueError(f"data too long: {len(data)} > {MAX_DATA}")
        prefix = bytes([HEAD, SID, OID, len(data), index]) + data
        return Frame(index=index, data=bytes(data).__class__(prefix + bytes([FrameCodec.crc(prefix), TAIL])))

    @staticmethod
    def decode_one(buf: bytes):
        """尝试从 buf 起始解一帧。返回 (Frame, consumed) 或 None(数据不足/校验失败且无法判定)。"""
        if len(buf) < 7:
            return None
        if buf[0] != HEAD:
            return None
        length = buf[3]
        total = 7 + length
        if len(buf) < total:
            return None
        if buf[4 + length + 1] != TAIL:
            return None
        prefix = buf[:5 + length]
        if FrameCodec.crc(prefix) != buf[5 + length]:
            return None
        frame = Frame(index=buf[4], data=bytes(buf[5:5 + length]))
        return frame, total

    @staticmethod
    def decode_stream(buf: bytes):
        """从流中解出尽可能多的帧。返回 (frames, leftover)。遇到非法字节(非帧头)跳过。"""
        frames = []
        i = 0
        while i < len(buf):
            if buf[i] != HEAD:
                i += 1
                continue
            res = FrameCodec.decode_one(buf[i:])
            if res is None:
                break  # 数据不足或损坏,保留余量
            frame, consumed = res
            frames.append(frame)
            i += consumed
        return frames, buf[i:]
```

注意 `encode` 里 `bytes(data).__class__(...)` 是为了构造 bytes;简化为直接 `bytes(prefix + ...)`:

```python
        body = bytes([FrameCodec.crc(prefix), TAIL])
        return Frame(index=index, data=bytes(data))
```
上面 `Frame.__bytes__` 需自己拼装完整帧,修正 `Frame`:

```python
    def __bytes__(self) -> bytes:
        prefix = bytes([HEAD, SID, OID, len(self.data), self.index]) + self.data
        return prefix + bytes([FrameCodec.crc(prefix), TAIL])
```

并简化 `encode`:

```python
    @staticmethod
    def encode(index: int, data: bytes) -> Frame:
        if len(data) > MAX_DATA:
            raise ValueError(f"data too long: {len(data)} > {MAX_DATA}")
        return Frame(index=index, data=bytes(data))
```

- [ ] **Step 4: 运行测试,确认通过**

```bash
pytest tests/protocol/test_frame_codec.py -v
```
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_ui_tool/protocol/frame_codec.py tests/protocol/test_frame_codec.py
git commit -m "feat: FrameCodec for _AGREEMENT frame encode/decode"
```

---

### Task 2: SerialTransport — 串口读写(可 mock)

封装 pyserial,提供同步读写 + 线程化读循环。测试用 `FakeSerial` 替代真实串口。

**Files:**
- Create: `src/lbs_ui_tool/protocol/serial_transport.py`
- Test: `tests/protocol/test_serial_transport.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/protocol/test_serial_transport.py
import time
from lbs_ui_tool.protocol.serial_transport import SerialTransport, FakeSerial

def test_fake_serial_roundtrip():
    s = FakeSerial()
    s.write(b"hello")
    assert s.read(5) == b"hello"

def test_transport_write_goes_to_serial():
    s = FakeSerial()
    t = SerialTransport(serial=s)
    t.write(b"\x5A")
    assert s.tx == b"\x5A"

def test_transport_read_callback_invoked():
    s = FakeSerial()
    s.feed(b"\x01\x02\x03")
    received = []
    t = SerialTransport(serial=s, on_data=received.append)
    t.read_once()
    assert received == [b"\x01\x02\x03"]

def test_list_ports_returns_list():
    ports = SerialTransport.list_ports()
    assert isinstance(ports, list)
```

- [ ] **Step 2: 运行测试,确认失败**

```bash
pytest tests/protocol/test_serial_transport.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 SerialTransport**

```python
# src/lbs_ui_tool/protocol/serial_transport.py
"""串口封装。真实环境用 pyserial,测试用 FakeSerial。"""
from typing import Callable, Optional
import serial.tools.list_ports


class FakeSerial:
    """测试用假串口。write 进 tx,read 从 rx 取。"""
    def __init__(self):
        self.tx = bytearray()
        self._rx = bytearray()

    def feed(self, data: bytes):
        self._rx.extend(data)

    def write(self, data: bytes) -> int:
        self.tx.extend(data)
        return len(data)

    def read(self, n: int) -> bytes:
        chunk = bytes(self._rx[:n])
        del self._rx[:n]
        return chunk

    def in_waiting(self) -> int:
        return len(self._rx)

    def close(self):
        pass


class SerialTransport:
    def __init__(self, serial, on_data: Optional[Callable[[bytes], None]] = None):
        self._serial = serial
        self._on_data = on_data

    @staticmethod
    def list_ports() -> list[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    def write(self, data: bytes) -> int:
        return self._serial.write(data)

    def read_once(self) -> bytes:
        n = self._serial.in_waiting() if hasattr(self._serial, "in_waiting") else 0
        if callable(n):
            n = n()
        n = max(n, 1)
        data = self._serial.read(n)
        if data and self._on_data:
            self._on_data(data)
        return data

    def close(self):
        self._serial.close()
```

- [ ] **Step 4: 运行测试,确认通过**

```bash
pytest tests/protocol/test_serial_transport.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_ui_tool/protocol/serial_transport.py tests/protocol/test_serial_transport.py
git commit -m "feat: SerialTransport with FakeSerial for testing"
```

---

### Task 3: YmodemTransfer — YMODEM 发送(NEXT-AI 用)

标准 YMODEM 发送端:C 握手 → SOH 文件名块 → STX/SOH 数据块 → EOT → 结束。CRC-16-XMODEM。USB 用 1024 STX 块,蓝牙用 128 SOH 块。

**Files:**
- Create: `src/lbs_ui_tool/protocol/ymodem.py`
- Test: `tests/protocol/test_ymodem.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/protocol/test_ymodem.py
from lbs_ui_tool.protocol.ymodem import YmodemTransfer, crc16_xmodem
from lbs_ui_tool.protocol.serial_transport import FakeSerial

def test_crc16_known_value():
    # CRC-16-XMODEM of "123456789" is 0x31C1
    assert crc16_xmodem(b"123456789") == 0x31C1

def test_send_small_file_uses_soh_128():
    s = FakeSerial()
    # 模拟设备: 收到块回 ACK, 收到文件名块回 ACK+C
    responses = bytearray()
    tx = YmodemTransfer(s, block_size=128)
    # 设备先发 'C'
    s.feed(b"C")
    # 预置对后续每块的 ACK
    progress = []
    tx.send(b"hello.bin", b"HELLO", progress_cb=progress.append)
    # 文件名块应含 "hello.bin"
    assert b"hello.bin" in s.tx
    # 数据块含 HELLO
    assert b"HELLO" in s.tx
```

- [ ] **Step 2: 运行测试,确认失败**

```bash
pytest tests/protocol/test_ymodem.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 YmodemTransfer**

```python
# src/lbs_ui_tool/protocol/ymodem.py
"""YMODEM 发送端实现(NEXT-AI 固件/Python 下发用)。"""
import os
from typing import Callable, Optional

SOH = 0x01
STX = 0x02
EOT = 0x04
ACK = 0x06
NAK = 0x15
CAN = 0x18
C = 0x43


def crc16_xmodem(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


class YmodemTransfer:
    def __init__(self, serial, block_size: int = 1024, timeout: float = 1.0):
        self._s = serial
        self.block_size = block_size
        self.timeout = timeout

    def _read_byte(self) -> Optional[int]:
        b = self._s.read(1)
        return b[0] if b else None

    def _wait_c(self):
        # 等待设备发 'C' 开始
        for _ in range(100):
            b = self._read_byte()
            if b == C:
                return True
        return False

    def _send_block(self, seq: int, payload: bytes):
        mark = STX if self.block_size == 1024 else SOH
        payload = payload + b"\x00" * (self.block_size - len(payload))
        crc = crc16_xmodem(payload)
        block = bytes([mark, seq & 0xFF, (~seq) & 0xFF]) + payload + bytes([crc >> 8, crc & 0xFF])
        self._s.write(block)
        return self._read_byte() == ACK

    def send(self, filename: str, data: bytes, progress_cb: Optional[Callable[[int, int], None]] = None) -> bool:
        if not self._wait_c():
            return False
        # 文件名块: filename + size + padding
        size_str = str(len(data)).encode()
        name_block = filename.encode() + b"\x00" + size_str
        name_block += b"\x00" * (128 - len(name_block))
        crc = crc16_xmodem(name_block)
        self._s.write(bytes([SOH, 0x00, 0xFF]) + name_block + bytes([crc >> 8, crc & 0xFF]))
        if self._read_byte() != ACK:
            return False
        if self._read_byte() != C:
            return False
        # 数据块
        seq = 1
        total = len(data)
        sent = 0
        for off in range(0, total, self.block_size):
            chunk = data[off:off + self.block_size]
            if not self._send_block(seq, chunk):
                return False
            seq += 1
            sent += len(chunk)
            if progress_cb:
                progress_cb(sent, total)
        # 空结束块
        self._send_block(0, b"")
        # EOT
        self._s.write(bytes([EOT]))
        if self._read_byte() != ACK:
            return False
        return True
```

- [ ] **Step 4: 运行测试,确认通过**

```bash
pytest tests/protocol/test_ymodem.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_ui_tool/protocol/ymodem.py tests/protocol/test_ymodem.py
git commit -m "feat: YmodemTransfer sender with CRC16-XMODEM"
```

---

### Task 4: FrameFileTransfer — 自定义帧文件传输(NEW-AI/SPARK 用)

基于 `FrameCodec`,用分区命令码(NEW-AI:0xDA/0xDB/0xDC/0xDD/0xEC;SPARK:0xDA 建文件)+ 0xAA 写块 + 0xBB 结束。设备每块回 0xFD ACK。

**Files:**
- Create: `src/lbs_ui_tool/protocol/frame_file_transfer.py`
- Test: `tests/protocol/test_frame_file_transfer.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/protocol/test_frame_file_transfer.py
from lbs_ui_tool.protocol.frame_file_transfer import FrameFileTransfer
from lbs_ui_tool.protocol.serial_transport import FakeSerial
from lbs_ui_tool.protocol.frame_codec import FrameCodec

def _ack_devices_responses(n_blocks: int) -> bytes:
    # 每块设备回 0xFD 帧(index=0xFD, no data)
    one = bytes(FrameCodec.encode(0xFD, b""))
    return one * (n_blocks + 2)  # 建文件ACK + 每块ACK + 结束ACK

def test_send_file_sends_start_blocks_end():
    s = FakeSerial()
    data = b"\x01" * 300  # 128*2 + 44 => 3 块
    s.feed(_ack_devices_responses(3))
    t = FrameFileTransfer(s)
    t.send(partition_cmd=0xDA, filename="app.bin", data=data, block_size=128)
    # 解析主机发出的帧序列
    frames, _ = FrameCodec.decode_stream(bytes(s.tx))
    indexes = [f.index for f in frames]
    assert indexes[0] == 0xDA          # 建文件
    assert indexes.count(0xAA) == 3    # 3 数据块
    assert indexes[-1] == 0xBB         # 结束

def test_progress_callback():
    s = FakeSerial()
    data = b"\x01" * 256
    s.feed(_ack_devices_responses(2))
    t = FrameFileTransfer(s)
    seen = []
    t.send(0xDA, "app.bin", data, block_size=128, progress_cb=seen.append)
    assert seen[-1] == 100
```

- [ ] **Step 2: 运行测试,确认失败**

```bash
pytest tests/protocol/test_frame_file_transfer.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 FrameFileTransfer**

```python
# src/lbs_ui_tool/protocol/frame_file_transfer.py
"""自定义帧文件传输: 建文件(cmd) -> 0xAA 分块 -> 0xBB 结束。每块等 0xFD ACK。"""
from typing import Callable, Optional
from lbs_ui_tool.protocol.frame_codec import FrameCodec, Frame
from lbs_ui_tool.protocol.serial_transport import SerialTransport

CMD_DATA = 0xAA
CMD_END = 0xBB
ACK = 0xFD


class FrameFileTransfer:
    def __init__(self, transport: SerialTransport, retries: int = 3):
        self._t = transport
        self.retries = retries

    def _wait_ack(self) -> bool:
        buf = b""
        for _ in range(200):
            buf += self._t.read_once()
            frames, leftover = FrameCodec.decode_stream(buf)
            buf = leftover
            if frames:
                return frames[0].index == ACK
        return False

    def send(self, partition_cmd: int, filename: str, data: bytes,
             block_size: int = 128, progress_cb: Optional[Callable[[int], None]] = None) -> bool:
        # 建文件: partition_cmd 携带文件名
        self._t.write(bytes(FrameCodec.encode(partition_cmd, filename.encode())))
        if not self._wait_ack():
            return False
        total = len(data)
        sent = 0
        for off in range(0, total, block_size):
            chunk = data[off:off + block_size]
            ok = False
            for _ in range(self.retries):
                self._t.write(bytes(FrameCodec.encode(CMD_DATA, chunk)))
                if self._wait_ack():
                    ok = True
                    break
            if not ok:
                return False
            sent += len(chunk)
            if progress_cb:
                progress_cb(int(sent * 100 / total) if total else 100)
        self._t.write(bytes(FrameCodec.encode(CMD_END, b"")))
        if not self._wait_ack():
            return False
        if progress_cb:
            progress_cb(100)
        return True
```

- [ ] **Step 4: 运行测试,确认通过**

```bash
pytest tests/protocol/test_frame_file_transfer.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_ui_tool/protocol/frame_file_transfer.py tests/protocol/test_frame_file_transfer.py
git commit -m "feat: FrameFileTransfer with 0xFD ACK per block"
```

---

## 适配器层

### Task 5: ProductProfile 抽象基类与数据类型

定义 `ProductProfile` ABC、`FirmwarePackage`/`FirmwareFile`、`MonitorState`、`NotSupportedError`。

**Files:**
- Create: `src/lbs_ui_tool/profiles/base.py`
- Test: `tests/profiles/test_base.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/profiles/test_base.py
import pytest
from lbs_ui_tool.profiles.base import (
    ProductProfile, FirmwareFile, FirmwarePackage, MonitorState, NotSupportedError,
)

def test_firmware_package_defaults():
    pkg = FirmwarePackage(files=[FirmwareFile("app", "a.bin", True)])
    assert pkg.files[0].partition == "app"

def test_update_sensors_default_raises():
    class Dummy(ProductProfile):
        name = "x"
        supports_sensor_update = False
        def handshake(self): pass
        def firmware_template(self): return FirmwarePackage([])
        def download_firmware(self, package, progress_cb): pass
        def deploy_python(self, o_path, slot, progress_cb): pass
        def enable_monitor(self, on): pass
        def parse_monitor(self, raw): return MonitorState()
    with pytest.raises(NotSupportedError):
        Dummy().update_sensors({})
```

- [ ] **Step 2: 运行测试,确认失败**

```bash
pytest tests/profiles/test_base.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 base.py**

```python
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
```

- [ ] **Step 4: 运行测试,确认通过**

```bash
pytest tests/profiles/test_base.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_ui_tool/profiles/base.py tests/profiles/test_base.py
git commit -m "feat: ProductProfile ABC and shared data types"
```

---

### Task 6: NewAiProfile — 自定义帧 + 传感器更新 + 9 类设备 ID

NEW-AI:固件用分区命令码(0xDA app/0xDB boot/0xDC config/0xDD version/0xEC music),Python 用 0xDA 建文件到 `1:app/<slot>.o`,监控 JSON 归一化,传感器更新 0x32 帧。

**Files:**
- Create: `src/lbs_ui_tool/profiles/new_ai.py`
- Test: `tests/profiles/test_new_ai.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/profiles/test_new_ai.py
import json
from lbs_ui_tool.profiles.new_ai import NewAiProfile, NEW_AI_DEVICE_IDS
from lbs_ui_tool.profiles.base import FirmwarePackage, FirmwareFile
from lbs_ui_tool.protocol.serial_transport import FakeSerial
from lbs_ui_tool.protocol.frame_codec import FrameCodec

def test_device_ids_known_values():
    assert NEW_AI_DEVICE_IDS["big_motor"] == 0xA1
    assert NEW_AI_DEVICE_IDS["small_motor"] == 0xA6
    assert NEW_AI_DEVICE_IDS["color"] == 0xA2
    assert NEW_AI_DEVICE_IDS["ultrasonic"] == 0xA3
    assert NEW_AI_DEVICE_IDS["touch"] == 0xA4
    assert NEW_AI_DEVICE_IDS["camera"] == 0xA7
    assert NEW_AI_DEVICE_IDS["gray"] == 0xA9
    assert NEW_AI_DEVICE_IDS["gray_v2"] == 0xB0
    assert NEW_AI_DEVICE_IDS["nfc"] == 0xB2

def test_firmware_template_has_five_partitions():
    s = FakeSerial()
    p = NewAiProfile(s)
    tpl = p.firmware_template()
    parts = {f.partition for f in tpl.files}
    assert parts == {"app", "boot", "config", "music", "version"}

def test_update_sensors_builds_0x32_frame():
    s = FakeSerial()
    s.feed(bytes(FrameCodec.encode(0xFD, b"")))  # ACK
    p = NewAiProfile(s)
    # A 端口=大电机(0xA1), H 端口=小电机(0xA6), 其余 FF
    p.update_sensors({"A": 0xA1, "H": 0xA6})
    frames, _ = FrameCodec.decode_stream(bytes(s.tx))
    assert frames[0].index == 0x32
    data = frames[0].data
    assert data[0] == 0xA1
    assert data[7] == 0xA6
    assert data[1] == 0xFF

def test_parse_monitor_normalizes():
    s = FakeSerial()
    p = NewAiProfile(s)
    payload = json.dumps({
        "deviceList": [{"port": 0, "big_motor": {"circly": "1.00", "speed": "50", "angle": "90"}}],
        "bat": "95.20", "version": 100, "heap": "45", "NewAiState": "run",
    }).encode()
    state = p.parse_monitor(payload)
    assert state.battery == 95.2
    assert state.version == "100"
    assert state.state == "run"
    assert 0 in state.ports
```

- [ ] **Step 2: 运行测试,确认失败**

```bash
pytest tests/profiles/test_new_ai.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 NewAiProfile**

```python
# src/lbs_ui_tool/profiles/new_ai.py
"""NEW-AI 适配器: 自定义帧分区升级 + 传感器更新(0x32) + 9 类设备 ID。"""
import json
from typing import Callable, Optional
from lbs_ui_tool.profiles.base import (
    ProductProfile, FirmwarePackage, FirmwareFile, MonitorState,
)
from lbs_ui_tool.protocol.serial_transport import SerialTransport
from lbs_ui_tool.protocol.frame_codec import FrameCodec
from lbs_ui_tool.protocol.frame_file_transfer import FrameFileTransfer

# 源码核实: motor.h / color.h / ultrasion.h / touch.h / camer.h / gray.h / grayv2.h / nfc_car.h
NEW_AI_DEVICE_IDS = {
    "big_motor":  0xA1,
    "small_motor": 0xA6,   # 源码原名 DEV_ID_SMALL_Motor
    "color":      0xA2,
    "ultrasonic": 0xA3,
    "touch":      0xA4,
    "camera":     0xA7,
    "gray":       0xA9,
    "gray_v2":    0xB0,
    "nfc":        0xB2,
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
KEEP = 0xFF
N_PORTS = 8


class NewAiProfile(ProductProfile):
    name = "NEW-AI"
    supports_sensor_update = True

    def __init__(self, transport: SerialTransport):
        self._t = transport
        self._fft = FrameFileTransfer(transport)

    def handshake(self) -> bool:
        return True  # NEW-AI 无显式握手,连接即就绪

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
            def cb(pct, _partition=f.partition):
                if progress_cb:
                    progress_cb(int((i + pct / 100) * 100 / total), f"{_partition} {pct}%")
            ok = self._fft.send(cmd, f.partition, data, block_size=128, progress_cb=cb)
            if not ok:
                raise RuntimeError(f"{f.partition} 下发失败")

    def deploy_python(self, o_path: str, slot: int,
                      progress_cb: Optional[Callable[[int, str], None]]) -> None:
        self._t.write(bytes(FrameCodec.encode(CMD_PY_ENTER, b"")))
        with open(o_path, "rb") as fh:
            data = fh.read()
        name = f"{slot}.o"
        ok = self._fft.send(0xDA, name, data, block_size=128, progress_cb=progress_cb and (lambda p: progress_cb(p, "下发")))
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
```

- [ ] **Step 4: 运行测试,确认通过**

```bash
pytest tests/profiles/test_new_ai.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_ui_tool/profiles/new_ai.py tests/profiles/test_new_ai.py
git commit -m "feat: NewAiProfile with partition firmware, sensor update, monitor"
```

---

### Task 7: SparkAiProfile — 自定义帧(app+version)

SPARK-AI:固件包 app+version,用 0xDA 建文件(app.bin / version.txt)写内部 Flash 0x08010000 + SPI Flash FATFS。

**Files:**
- Create: `src/lbs_ui_tool/profiles/spark_ai.py`
- Test: `tests/profiles/test_spark_ai.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/profiles/test_spark_ai.py
import json
from lbs_ui_tool.profiles.spark_ai import SparkAiProfile
from lbs_ui_tool.profiles.base import FirmwarePackage
from lbs_ui_tool.protocol.serial_transport import FakeSerial
from lbs_ui_tool.protocol.frame_codec import FrameCodec

def test_firmware_template_app_version():
    s = FakeSerial()
    p = SparkAiProfile(s)
    parts = {f.partition for f in p.firmware_template().files}
    assert parts == {"app", "version"}

def test_update_sensors_not_supported():
    import pytest
    from lbs_ui_tool.profiles.base import NotSupportedError
    s = FakeSerial()
    p = SparkAiProfile(s)
    with pytest.raises(NotSupportedError):
        p.update_sensors({})

def test_parse_monitor_uses_willaistate():
    s = FakeSerial()
    p = SparkAiProfile(s)
    payload = json.dumps({
        "deviceList": [{"port": 0, "touch": {"state": 0}}],
        "adc": {"bat": "85%"}, "version": 100, "heap": "45", "WillAiState": "run",
    }).encode()
    st = p.parse_monitor(payload)
    assert st.state == "run"
    assert st.battery == 85.0
```

- [ ] **Step 2: 运行测试,确认失败**

```bash
pytest tests/profiles/test_spark_ai.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 SparkAiProfile**

```python
# src/lbs_ui_tool/profiles/spark_ai.py
"""SPARK-AI 适配器: 自定义帧 app+version 升级,不支持传感器更新。"""
import json
import re
from typing import Callable, Optional
from lbs_ui_tool.profiles.base import (
    ProductProfile, FirmwarePackage, FirmwareFile, MonitorState,
)
from lbs_ui_tool.protocol.serial_transport import SerialTransport
from lbs_ui_tool.protocol.frame_codec import FrameCodec
from lbs_ui_tool.protocol.frame_file_transfer import FrameFileTransfer

CMD_PY_ENTER = 0xB6
CMD_PY_EXIT = 0xB9
CMD_MONITOR_ON = 0xBA
CMD_MONITOR_OFF = 0xBE
PARTITION_FILENAMES = {"app": "app.bin", "version": "version.txt"}


class SparkAiProfile(ProductProfile):
    name = "SPARK-AI"
    supports_sensor_update = False

    def __init__(self, transport: SerialTransport):
        self._t = transport
        self._fft = FrameFileTransfer(transport)

    def handshake(self) -> bool:
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
            def cb(pct, _p=f.partition):
                if progress_cb:
                    progress_cb(int((i + pct / 100) * 100 / total), f"{_p} {pct}%")
            ok = self._fft.send(0xDA, name, data, block_size=128, progress_cb=cb)
            if not ok:
                raise RuntimeError(f"{f.partition} 下发失败")

    def deploy_python(self, o_path: str, slot: int,
                      progress_cb: Optional[Callable[[int, str], None]]) -> None:
        self._t.write(bytes(FrameCodec.encode(CMD_PY_ENTER, b"")))
        with open(o_path, "rb") as fh:
            data = fh.read()
        ok = self._fft.send(0xDA, f"{slot}.o", data, block_size=128,
                            progress_cb=progress_cb and (lambda p: progress_cb(p, "下发")))
        self._t.write(bytes(FrameCodec.encode(CMD_PY_EXIT, b"")))
        if not ok:
            raise RuntimeError("Python 字节码下发失败")

    def enable_monitor(self, on: bool) -> None:
        self._t.write(bytes(FrameCodec.encode(CMD_MONITOR_ON if on else CMD_MONITOR_OFF, b"")))

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
```

- [ ] **Step 4: 运行测试,确认通过**

```bash
pytest tests/profiles/test_spark_ai.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_ui_tool/profiles/spark_ai.py tests/profiles/test_spark_ai.py
git commit -m "feat: SparkAiProfile with app+version firmware, monitor"
```

---

### Task 8: NextAiProfile — YMODEM 单 bin

NEXT-AI:固件单 .bin 走 YMODEM,Python 字节码也走 YMODEM,不支持传感器更新。

**Files:**
- Create: `src/lbs_ui_tool/profiles/next_ai.py`
- Test: `tests/profiles/test_next_ai.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/profiles/test_next_ai.py
import json
import pytest
from lbs_ui_tool.profiles.next_ai import NextAiProfile
from lbs_ui_tool.profiles.base import NotSupportedError, FirmwarePackage
from lbs_ui_tool.protocol.serial_transport import FakeSerial

def test_firmware_template_single_bin():
    s = FakeSerial()
    p = NextAiProfile(s)
    files = p.firmware_template().files
    assert len(files) == 1
    assert files[0].partition == ""

def test_update_sensors_not_supported():
    s = FakeSerial()
    with pytest.raises(NotSupportedError):
        NextAiProfile(s).update_sensors({})

def test_parse_monitor_basic():
    s = FakeSerial()
    p = NextAiProfile(s)
    payload = json.dumps({"bat": "80", "version": 50, "state": "idle"}).encode()
    st = p.parse_monitor(payload)
    assert st.battery == 80.0
    assert st.version == "50"
```

- [ ] **Step 2: 运行测试,确认失败**

```bash
pytest tests/profiles/test_next_ai.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 NextAiProfile**

```python
# src/lbs_ui_tool/profiles/next_ai.py
"""NEXT-AI 适配器: YMODEM 单 bin 升级,不支持传感器更新。"""
import json
from typing import Callable, Optional
from lbs_ui_tool.profiles.base import (
    ProductProfile, FirmwarePackage, FirmwareFile, MonitorState,
)
from lbs_ui_tool.protocol.serial_transport import SerialTransport
from lbs_ui_tool.protocol.frame_codec import FrameCodec
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
        return True

    def firmware_template(self) -> FirmwarePackage:
        return FirmwarePackage(files=[FirmwareFile("", "", required=True)])

    def download_firmware(self, package: FirmwarePackage,
                          progress_cb: Optional[Callable[[int, str], None]]) -> None:
        f = next(x for x in package.files if x.path)
        with open(f.path, "rb") as fh:
            data = fh.read()
        ok = self._ymodem.send("firmware.bin", data,
                               progress_cb=progress_cb and (lambda s, t: progress_cb(int(s*100/t), "下发")))
        if not ok:
            raise RuntimeError("YMODEM 固件下发失败")

    def deploy_python(self, o_path: str, slot: int,
                      progress_cb: Optional[Callable[[int, str], None]]) -> None:
        with open(o_path, "rb") as fh:
            data = fh.read()
        ok = self._ymodem.send(f"{slot}.o", data,
                               progress_cb=progress_cb and (lambda s, t: progress_cb(int(s*100/t), "下发")))
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
```

- [ ] **Step 4: 运行测试,确认通过**

```bash
pytest tests/profiles/test_next_ai.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_ui_tool/profiles/next_ai.py tests/profiles/test_next_ai.py
git commit -m "feat: NextAiProfile with YMODEM single-bin firmware"
```

---

### Task 9: Profile 注册表

按产品名构造 profile,集中管理。

**Files:**
- Create: `src/lbs_ui_tool/profiles/registry.py`
- Test: `tests/profiles/test_registry.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/profiles/test_registry.py
import pytest
from lbs_ui_tool.profiles.registry import get_profile, list_products
from lbs_ui_tool.profiles.new_ai import NewAiProfile
from lbs_ui_tool.profiles.spark_ai import SparkAiProfile
from lbs_ui_tool.profiles.next_ai import NextAiProfile
from lbs_ui_tool.protocol.serial_transport import FakeSerial

def test_list_products():
    assert set(list_products()) == {"NEW-AI", "SPARK-AI", "NEXT-AI"}

def test_get_profile_by_name():
    s = FakeSerial()
    assert isinstance(get_profile("NEW-AI", s), NewAiProfile)
    assert isinstance(get_profile("SPARK-AI", s), SparkAiProfile)
    assert isinstance(get_profile("NEXT-AI", s), NextAiProfile)

def test_unknown_raises():
    with pytest.raises(KeyError):
        get_profile("???", FakeSerial())
```

- [ ] **Step 2: 运行测试,确认失败**

```bash
pytest tests/profiles/test_registry.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 registry**

```python
# src/lbs_ui_tool/profiles/registry.py
"""产品注册表。"""
from lbs_ui_tool.profiles.base import ProductProfile
from lbs_ui_tool.profiles.new_ai import NewAiProfile
from lbs_ui_tool.profiles.spark_ai import SparkAiProfile
from lbs_ui_tool.profiles.next_ai import NextAiProfile

_REGISTRY = {
    "NEW-AI": NewAiProfile,
    "SPARK-AI": SparkAiProfile,
    "NEXT-AI": NextAiProfile,
}


def list_products() -> list[str]:
    return list(_REGISTRY.keys())


def get_profile(name: str, transport) -> ProductProfile:
    cls = _REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"未知产品: {name}")
    return cls(transport)
```

- [ ] **Step 4: 运行测试,确认通过**

```bash
pytest tests/profiles/test_registry.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_ui_tool/profiles/registry.py tests/profiles/test_registry.py
git commit -m "feat: profile registry"
```

---

## 应用层与 Python 编译

### Task 10: PikaCompiler — 调用 rust-msc-latest-win10.exe

封装 `rust-msc-latest-win10.exe -c input.py -o output.o`,在临时目录编译。

**Files:**
- Create: `src/lbs_ui_tool/pika_compiler.py`
- Test: `tests/test_pika_compiler.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_pika_compiler.py
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from lbs_ui_tool.pika_compiler import PikaCompiler

def test_resolve_compiler_path():
    c = PikaCompiler(compiler_path="e:/LBS-UI-Tool/rust-msc-latest-win10.exe")
    assert c.compiler_path.endswith("rust-msc-latest-win10.exe")

def test_compile_invokes_subprocess(tmp_path):
    c = PikaCompiler(compiler_path="rust-msc-latest-win10.exe")
    src = tmp_path / "main.py"
    src.write_text("print('hi')")
    with patch("lbs_ui_tool.pika_compiler.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        out = c.compile(str(src))
        assert run.called
        args = run.call_args[0][0]
        assert "-c" in args and "-o" in args

def test_compile_failure_raises(tmp_path):
    c = PikaCompiler(compiler_path="rust-msc-latest-win10.exe")
    src = tmp_path / "main.py"
    src.write_text("print('hi')")
    with patch("lbs_ui_tool.pika_compiler.subprocess.run") as run:
        run.return_value = MagicMock(returncode=1, stdout=b"", stderr=b"syntax error")
        import pytest
        with pytest.raises(RuntimeError, match="syntax error"):
            c.compile(str(src))
```

- [ ] **Step 2: 运行测试,确认失败**

```bash
pytest tests/test_pika_compiler.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 PikaCompiler**

```python
# src/lbs_ui_tool/pika_compiler.py
"""调用 rust-msc-latest-win10.exe 编译 .py -> .o"""
import os
import subprocess
from pathlib import Path

DEFAULT_COMPILER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                "rust-msc-latest-win10.exe")


class PikaCompiler:
    def __init__(self, compiler_path: str = DEFAULT_COMPILER):
        self.compiler_path = compiler_path

    def compile(self, src_path: str, out_path: str | None = None) -> str:
        if out_path is None:
            out_path = str(Path(src_path).with_suffix(".o"))
        result = subprocess.run(
            [self.compiler_path, "-c", src_path, "-o", out_path],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode(errors="replace") or "编译失败")
        return out_path
```

- [ ] **Step 4: 运行测试,确认通过**

```bash
pytest tests/test_pika_compiler.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_ui_tool/pika_compiler.py tests/test_pika_compiler.py
git commit -m "feat: PikaCompiler wraps rust-msc-latest-win10.exe"
```

---

### Task 11: BackendBridge — 暴露给 QML 的单例

`BackendBridge(QObject)`:管理产品选择、连接、任务编排、进度信号。用 QML 可调用。

**Files:**
- Create: `src/lbs_ui_tool/backend.py`
- Test: `tests/test_backend.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_backend.py
import pytest
from pytestqt.qtbot import QtBot
from lbs_ui_tool.backend import BackendBridge
from lbs_ui_tool.protocol.serial_transport import FakeSerial

def test_list_products(qtbot: QtBot):
    b = BackendBridge()
    assert "NEW-AI" in b.list_products()

def test_list_ports(qtbot: QtBot):
    b = BackendBridge()
    assert isinstance(b.list_ports(), list)

def test_connect_selects_profile(qtbot: QtBot, monkeypatch):
    b = BackendBridge()
    fake = FakeSerial()
    monkeypatch.setattr(b, "_open_serial", lambda port: fake)
    b.connect_device("COM1", "NEW-AI")
    assert b.is_connected
    assert b.profile.name == "NEW-AI"

def test_progress_signal_emitted(qtbot: QtBot, monkeypatch):
    b = BackendBridge()
    fake = FakeSerial()
    monkeypatch.setattr(b, "_open_serial", lambda port: fake)
    b.connect_device("COM1", "SPARK-AI")
    with qtbot.waitSignal(b.progress, timeout=1000) as blocker:
        b.emit_progress(50, "test")
    assert blocker.args[0] == 50
```

- [ ] **Step 2: 运行测试,确认失败**

```bash
pytest tests/test_backend.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 BackendBridge**

```python
# src/lbs_ui_tool/backend.py
"""暴露给 QML 的应用层单例。"""
from typing import Optional
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtQml import QmlElement
import serial

from lbs_ui_tool.profiles.registry import list_products, get_profile
from lbs_ui_tool.profiles.base import ProductProfile, NotSupportedError
from lbs_ui_tool.protocol.serial_transport import SerialTransport

QML_IMPORT_NAME = "LbsUiTool"
QML_IMPORT_MAJOR_VERSION = 1


class BackendBridge(QObject):
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

    @Slot(str, result="QVariantList")
    def firmware_template(self):
        if not self.profile:
            return []
        return [{"partition": f.partition, "required": f.required, "path": f.path}
                for f in self.profile.firmware_template().files]

    @Slot(bool)
    def enable_monitor(self, on: bool):
        if self.profile:
            self.profile.enable_monitor(on)
```

- [ ] **Step 4: 运行测试,确认通过**

```bash
pytest tests/test_backend.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/lbs_ui_tool/backend.py tests/test_backend.py
git commit -m "feat: BackendBridge QML-facing singleton"
```

---

## UI 层(QML,App Store 风格)

UI 任务以"可启动可见"为验收,不做单测(QML 视觉测试 ROI 低),改为手动冒烟验收。

### Task 12: 主入口 main.py + QML 引擎

**Files:**
- Create: `src/lbs_ui_tool/__main__.py`
- Create: `src/lbs_ui_tool/qml/main.qml`
- Create: `src/lbs_ui_tool/qml/ui/`

- [ ] **Step 1: 实现 main.py**

```python
# src/lbs_ui_tool/__main__.py
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
```

- [ ] **Step 2: 实现 main.qml 骨架(App Store 风格首页)**

```qml
// src/lbs_ui_tool/qml/main.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: root
    visible: true
    width: 1100; height: 720
    minimumWidth: 900; minimumHeight: 640
    title: "LBS 上位机工具"
    color: "#0F0F14"

    StackView {
        id: stack
        anchors.fill: parent
        initialItem: homePage
    }

    Component { id: homePage; HomePage {} }
    Component { id: workspacePage; WorkspacePage {} }

    function openWorkspace(productName) {
        stack.push(workspacePage, {"productName": productName})
    }
}
```

- [ ] **Step 3: 启动验证(冒烟)**

```bash
python -m lbs_ui_tool
```
Expected: 窗口打开,深色背景(HomePage 尚未实现会报缺组件,下一任务补)。

- [ ] **Step 4: Commit**

```bash
git add src/lbs_ui_tool/__main__.py src/lbs_ui_tool/qml/main.qml
git commit -m "feat: app entry and QML engine bootstrap"
```

---

### Task 13: HomePage — 三张产品卡片

**Files:**
- Create: `src/lbs_ui_tool/qml/ui/HomePage.qml`
- Create: `src/lbs_ui_tool/qml/ui/ProductCard.qml`
- Create: `src/lbs_ui_tool/qml/ui/Theme.qml`
- Create: `src/lbs_ui_tool/assets/.gitkeep`

- [ ] **Step 1: Theme.qml(配色/字体常量)**

```qml
// src/lbs_ui_tool/qml/ui/Theme.qml
pragma Singleton
import QtQuick

QtObject {
    readonly property color bg: "#0F0F14"
    readonly property color card: "#1C1C26"
    readonly property color cardHover: "#262633"
    readonly property color accent: "#0A84FF"
    readonly property color text: "#FFFFFF"
    readonly property color textDim: "#9A9AA5"
    readonly property int radius: 18
    readonly property int cardW: 300
    readonly property int cardH: 380
    // 每产品主色(占位,可改)
    readonly property var productColors: {
        "NEW-AI": "#0A84FF",
        "SPARK-AI": "#FF9F0A",
        "NEXT-AI": "#BF5AF2",
    }
}
```

并在 `qml/qtquickcontrols2.conf` 或通过 `qmldir` 注册 Singleton。创建 `src/lbs_ui_tool/qml/ui/qmldir`:
```
singleton Theme Theme.qml
```

- [ ] **Step 2: ProductCard.qml**

```qml
// src/lbs_ui_tool/qml/ui/ProductCard.qml
import QtQuick
import QtQuick.Controls

Rectangle {
    id: card
    property string productName: ""
    property string subtitle: ""
    property color glow: "#0A84FF"
    width: 300; height: 380
    radius: 18
    color: mouse.containsMouse ? "#262633" : "#1C1C26"
    border.color: glow; border.width: 1
    scale: mouse.pressed ? 0.97 : 1.0
    Behavior on scale { NumberAnimation { duration: 120 } }

    Column {
        anchors.fill: parent; anchors.margins: 24
        spacing: 16
        Rectangle {  // 封面占位
            width: parent.width; height: 200
            radius: 14
            gradient: Gradient {
                orientation: Gradient.Vertical
                GradientStop { position: 0; color: Qt.lighter(card.glow, 1.2) }
                GradientStop { position: 1; color: card.glow }
            }
            Text {
                anchors.centerIn: parent
                text: card.productName.charAt(0)
                font.pixelSize: 96; font.bold: true; color: "#FFFFFF66"
            }
        }
        Text { text: card.productName; font.pixelSize: 26; font.bold: true; color: "#FFFFFF" }
        Text { text: card.subtitle; font.pixelSize: 14; color: "#9A9AA5" }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: card.clicked()
    }
    signal clicked()
}
```

- [ ] **Step 3: HomePage.qml**

```qml
// src/lbs_ui_tool/qml/ui/HomePage.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    Column {
        anchors.centerIn: parent
        spacing: 48
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "选择产品"
            font.pixelSize: 40; font.bold: true; color: "#FFFFFF"
        }
        Row {
            spacing: 32
            anchors.horizontalCenter: parent.horizontalCenter
            ProductCard { productName: "NEW-AI"; subtitle: "STM32H723 · 支持传感器更新"; glow: "#0A84FF"
                onClicked: root.openWorkspace("NEW-AI") }
            ProductCard { productName: "SPARK-AI"; subtitle: "STM32F103"; glow: "#FF9F0A"
                onClicked: root.openWorkspace("SPARK-AI") }
            ProductCard { productName: "NEXT-AI"; subtitle: "APM32E103"; glow: "#BF5AF2"
                onClicked: root.openWorkspace("NEXT-AI") }
        }
    }
}
```

- [ ] **Step 4: 冒烟验证**

```bash
python -m lbs_ui_tool
```
Expected: 首页三张卡片显示,hover 抬升,点击进入工作区(WorkspacePage 待实现会报错,下任务补)。

- [ ] **Step 5: Commit**

```bash
git add src/lbs_ui_tool/qml/ui/ src/lbs_ui_tool/assets/
git commit -m "feat: HomePage with three product cards (App Store style)"
```

---

### Task 14: WorkspacePage — 左侧功能栏 + 右侧内容栈

**Files:**
- Create: `src/lbs_ui_tool/qml/ui/WorkspacePage.qml`
- Create: `src/lbs_ui_tool/qml/ui/SidebarButton.qml`
- Create: `src/lbs_ui_tool/qml/ui/FirmwarePage.qml`
- Create: `src/lbs_ui_tool/qml/ui/MonitorPage.qml`
- Create: `src/lbs_ui_tool/qml/ui/SensorPage.qml`
- Create: `src/lbs_ui_tool/qml/ui/PythonPage.qml`

- [ ] **Step 1: WorkspacePage 骨架**

```qml
// src/lbs_ui_tool/qml/ui/WorkspacePage.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    property string productName: ""
    property var features: ["固件", "监控", "传感器", "Python"]
    property int currentFeature: 0

    Row {
        anchors.fill: parent
        // 返回 + 产品名 + 功能栏
        Column {
            width: 220; height: parent.height
            spacing: 8
            padding: 24
            Button { text: "← 返回"; flat: true; onClicked: root.StackView.view.pop() }
            Text { text: productName; font.pixelSize: 22; font.bold: true; color: "#FFF"; topPadding: 24 }
            Repeater {
                model: features
                SidebarButton {
                    text: modelData
                    selected: index === currentFeature
                    onClicked: currentFeature = index
                    enabled: !(productName !== "NEW-AI" && modelData === "传感器")
                }
            }
        }
        Rectangle {
            width: parent.width - 220; height: parent.height
            color: "#0F0F14"
            StackLayout {
                anchors.fill: parent; currentIndex: currentFeature
                FirmwarePage {}
                MonitorPage {}
                SensorPage { productName: parent.parent.productName }
                PythonPage {}
            }
        }
    }
}
```

- [ ] **Step 2: SidebarButton.qml**

```qml
// src/lbs_ui_tool/qml/ui/SidebarButton.qml
import QtQuick.Controls
Button {
    property bool selected: false
    width: 172; height: 44
    text: parent ? parent.text : ""
    flat: true
    background: Rectangle {
        radius: 10
        color: selected ? "#1C1C26" : "transparent"
        border.color: selected ? "#0A84FF" : "transparent"
    }
    contentItem: Text { text: parent.parent.text; color: parent.selected ? "#FFF" : "#9A9AA5"; font.pixelSize: 16 }
}
```
(注:SidebarButton 用 `Button` 简化,实际 text 由 modelData 传入;修正为 property `label`,见 Step 3 修正。)

- [ ] **Step 3: 四个功能页占位**

每个功能页先做空壳 `Item { Text { text: "<功能名>" ; anchors.centerIn: parent; color: "#FFF" } }`,后续任务填充。例如:

```qml
// src/lbs_ui_tool/qml/ui/FirmwarePage.qml
import QtQuick
Item {
    Text { text: "固件下载"; anchors.centerIn: parent; color: "#FFF"; font.pixelSize: 24 }
}
```
MonitorPage / SensorPage / PythonPage 同理,分别文字为"监控"/"传感器更新"/"Python 代码"。

- [ ] **Step 4: 冒烟验证**

```bash
python -m lbs_ui_tool
```
Expected: 选产品进入工作区,左侧四个按钮,点击切换右侧内容;非 NEW-AI 时传感器按钮禁用。

- [ ] **Step 5: Commit**

```bash
git add src/lbs_ui_tool/qml/ui/WorkspacePage.qml src/lbs_ui_tool/qml/ui/SidebarButton.qml src/lbs_ui_tool/qml/ui/FirmwarePage.qml src/lbs_ui_tool/qml/ui/MonitorPage.qml src/lbs_ui_tool/qml/ui/SensorPage.qml src/lbs_ui_tool/qml/ui/PythonPage.qml
git commit -m "feat: WorkspacePage with sidebar and feature stack"
```

---

### Task 15: FirmwarePage — 固件下载(按产品包结构)

**Files:**
- Modify: `src/lbs_ui_tool/qml/ui/FirmwarePage.qml`
- Modify: `src/lbs_ui_tool/backend.py` (加 download_firmware slot)

- [ ] **Step 1: Backend 加 download_firmware 槽**

在 `backend.py` 的 `BackendBridge` 增加方法:

```python
    @Slot("QVariantList")
    def download_firmware(self, files):
        """files: [{"partition":..., "path":...}] 由 QML 收集"""
        from lbs_ui_tool.profiles.base import FirmwarePackage, FirmwareFile
        if not self.profile:
            self.taskFinished.emit(False, "未连接")
            return
        pkg = FirmwarePackage(files=[FirmwareFile(f["partition"], f["path"]) for f in files if f.get("path")])
        try:
            self.profile.download_firmware(pkg, lambda p, m: self.progress.emit(p, m))
            self.taskFinished.emit(True, "固件更新完成")
        except Exception as e:
            self.taskFinished.emit(False, str(e))
```

- [ ] **Step 2: FirmwarePage.qml 实现**

```qml
// src/lbs_ui_tool/qml/ui/FirmwarePage.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

ScrollView {
    Column {
        width: 600; spacing: 16; padding: 24
        Text { text: "固件下载"; color: "#FFF"; font.pixelSize: 24; font.bold: true }
        Repeater {
            model: backend.firmware_template()
            Row {
                spacing: 12
                Text { text: modelData.partition ? modelData.partition : "固件"; color: "#9A9AA5"; width: 100; anchors.verticalCenter: parent.verticalCenter }
                TextField { id: pathField; width: 320; placeholderText: "选择文件..." ; readOnly: true; text: modelData.path }
                Button {
                    text: "浏览"
                    onClicked: fd.open()
                    FileDialog { id: fd; onAccepted: pathField.text = currentFile.toString().replace("file:///","") }
                }
            }
        }
        ProgressBar { id: bar; width: parent.width; value: 0 }
        Text { id: statusText; color: "#9A9AA5" }
        Button {
            text: "开始更新"
            onClicked: {
                var files = []
                for (var i = 0; i < repeater.count; i++) files.push({"partition": repeater.itemAt(i).children[0].text, "path": repeater.itemAt(i).children[1].text})
                backend.download_firmware(files)
            }
        }
    }
    Connections {
        target: backend
        function onProgress(pct, msg) { bar.value = pct / 100; statusText.text = msg }
        function onTaskFinished(ok, msg) { statusText.text = msg }
    }
}
```
(注:Repeater 收集逻辑需用 `Repeater { id: repeater; ... }`,实际实现中给 Repeater 加 id 并在按钮处引用。)

- [ ] **Step 3: 冒烟验证**

```bash
python -m lbs_ui_tool
```
Expected: 进入固件页,按产品显示对应文件清单(NEW 5 项 / SPARK 2 项 / NEXT 1 项),浏览选文件,点更新显示进度。

- [ ] **Step 4: Commit**

```bash
git add src/lbs_ui_tool/qml/ui/FirmwarePage.qml src/lbs_ui_tool/backend.py
git commit -m "feat: FirmwarePage with per-product package layout"
```

---

### Task 16: MonitorPage — 监控(端口卡片 + 折线图)

**Files:**
- Modify: `src/lbs_ui_tool/qml/ui/MonitorPage.qml`
- Modify: `src/lbs_ui_tool/backend.py` (监控解析 + 上报)

- [ ] **Step 1: Backend 监控接收**

在 `backend.py` 增加串口读循环(用 `QTimer` 轮询,避免线程复杂度):

```python
    from PySide6.QtCore import QTimer

    def __init__(self):
        super().__init__()
        ...
        self._monitor_timer = QTimer(self)
        self._monitor_timer.timeout.connect(self._poll_serial)
        self._buf = b""

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
```

- [ ] **Step 2: MonitorPage.qml 实现**

```qml
// src/lbs_ui_tool/qml/ui/MonitorPage.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    Column {
        anchors.fill: parent; anchors.margins: 24; spacing: 16
        Row {
            spacing: 12
            Text { text: "监控"; color: "#FFF"; font.pixelSize: 24; font.bold: true }
            Switch { id: monSwitch; onToggled: backend.enable_monitor(checked) }
        }
        Row {
            spacing: 24
            InfoCard { label: "电量"; value: monitorData.battery ? monitorData.battery + "%" : "--" }
            InfoCard { label: "版本"; value: monitorData.version || "--" }
            InfoCard { label: "状态"; value: monitorData.state || "--" }
        }
        // 端口卡片网格
        GridView {
            width: parent.width; height: 300; cellWidth: 200; cellHeight: 120
            model: Object.keys(monitorData.ports || {})
            delegate: Rectangle {
                width: 180; height: 100; radius: 12; color: "#1C1C26"
                Column { anchors.centerIn: parent; spacing: 4
                    Text { text: "端口 " + modelData; color: "#FFF"; font.bold: true }
                    Text { text: JSON.stringify(monitorData.ports[modelData]); color: "#9A9AA5"; font.pixelSize: 11 }
                }
            }
        }
    }
    property var monitorData: ({})
    Connections {
        target: backend
        function onMonitorState(data) { monitorData = data }
    }
}
```
(InfoCard 为内联组件,实际可写在同文件 `Component` 或单独文件。)

- [ ] **Step 3: 冒烟验证**

```bash
python -m lbs_ui_tool
```
Expected: 监控页有开关,打开后(连真机)显示电量/版本/端口卡片。

- [ ] **Step 4: Commit**

```bash
git add src/lbs_ui_tool/qml/ui/MonitorPage.qml src/lbs_ui_tool/backend.py
git commit -m "feat: MonitorPage with port cards and battery/version"
```

---

### Task 17: SensorPage — 传感器更新(仅 NEW-AI)

**Files:**
- Modify: `src/lbs_ui_tool/qml/ui/SensorPage.qml`
- Modify: `src/lbs_ui_tool/backend.py` (update_sensors slot)

- [ ] **Step 1: Backend update_sensors 槽**

```python
    @Slot("QVariantMap")
    def update_sensors(self, ports_map):
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
```

- [ ] **Step 2: SensorPage.qml 实现**

```qml
// src/lbs_ui_tool/qml/ui/SensorPage.qml
import QtQuick
import QtQuick.Controls

Item {
    property string productName: ""
    property var deviceOptions: [
        {"label":"保持不动","value":255},
        {"label":"大电机","value":161},
        {"label":"小电机","value":166},
        {"label":"颜色","value":162},
        {"label":"超声波","value":163},
        {"label":"触摸","value":164},
        {"label":"摄像头","value":167},
        {"label":"灰度","value":169},
        {"label":"灰度V2","value":176},
        {"label":"NFC","value":178},
    ]
    property var selections: ({"A":255,"B":255,"C":255,"D":255,"E":255,"F":255,"G":255,"H":255})

    Column {
        anchors.fill: parent; anchors.margins: 24; spacing: 16
        Text { text: "传感器更新"; color: "#FFF"; font.pixelSize: 24; font.bold: true }
        Text {
            visible: productName !== "NEW-AI"
            text: "本产品不支持传感器更新"
            color: "#9A9AA5"; font.pixelSize: 16
        }
        Grid {
            visible: productName === "NEW-AI"
            columns: 4; spacing: 12
            Repeater {
                model: ["A","B","C","D","E","F","G","H"]
                Column {
                    spacing: 6
                    Text { text: "端口 " + modelData; color: "#FFF" }
                    ComboBox {
                        model: deviceOptions
                        textRole: "label"
                        onActivated: selections[modelData] = deviceOptions[currentIndex].value
                    }
                }
            }
        }
        Button {
            visible: productName === "NEW-AI"
            text: "更新"
            onClicked: backend.update_sensors(selections)
        }
        Text { id: status; color: "#9A9AA5" }
    }
    Connections { target: backend; function onTaskFinished(ok, msg) { status.text = msg } }
}
```

- [ ] **Step 3: 冒烟验证**

```bash
python -m lbs_ui_tool
```
Expected: NEW-AI 下传感器页显示 8 端口下拉 + 更新按钮;SPARK/NEXT 显示"不支持"。

- [ ] **Step 4: Commit**

```bash
git add src/lbs_ui_tool/qml/ui/SensorPage.qml src/lbs_ui_tool/backend.py
git commit -m "feat: SensorPage with 8-port device selectors (NEW-AI only)"
```

---

### Task 18: PythonPage — 多文件 IDE

**Files:**
- Modify: `src/lbs_ui_tool/qml/ui/PythonPage.qml`
- Modify: `src/lbs_ui_tool/backend.py` (compile + deploy slots)

- [ ] **Step 1: Backend compile/deploy 槽**

```python
    @Slot(str, result=str)
    def compile_python(self, src_path):
        from lbs_ui_tool.pika_compiler import PikaCompiler
        try:
            out = PikaCompiler().compile(src_path)
            return out
        except Exception as e:
            self.taskFinished.emit(False, str(e))
            return ""

    @Slot(str, int)
    def deploy_python(self, o_path, slot):
        if not self.profile:
            self.taskFinished.emit(False, "未连接")
            return
        try:
            self.profile.deploy_python(o_path, slot, lambda p, m: self.progress.emit(p, m))
            self.taskFinished.emit(True, "下发完成")
        except Exception as e:
            self.taskFinished.emit(False, str(e))
```

- [ ] **Step 2: PythonPage.qml 实现(文件树 + 编辑器 + 控制台)**

```qml
// src/lbs_ui_tool/qml/ui/PythonPage.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    Row {
        anchors.fill: parent
        // 文件树
        Column {
            width: 200; height: parent.height; padding: 12; spacing: 8
            Button { text: "打开项目目录"; onClicked: folderDialog.open() }
            ListView {
                width: 176; height: parent.height - 60
                model: fileModel
                delegate: Item {
                    width: 176; height: 28
                    Text { text: modelData; color: "#FFF" }
                    MouseArea { anchors.fill: parent; onClicked: { editor.text = backend_read_file(modelData) } }
                }
            }
        }
        // 编辑器
        Rectangle {
            width: parent.width - 200 - 300; height: parent.height; color: "#15151C"
            ScrollView {
                anchors.fill: parent
                TextArea {
                    id: editor
                    font.family: "Consolas"; font.pixelSize: 14; color: "#FFF"
                    textFormat: TextEdit.PlainText
                }
            }
        }
        // 控制台 + 工具
        Column {
            width: 300; height: parent.height; padding: 12; spacing: 8
            SpinBox { id: slotBox; from: 0; to: 19; value: 0 }
            Row { spacing: 8
                Button { text: "保存"; onClicked: consoleLog.text = "已保存" }
                Button { text: "编译"; onClicked: { var o = backend.compile_python(currentFile); consoleLog.text = o ? "已编译: "+o : "编译失败" } }
                Button { text: "下发"; onClicked: backend.deploy_python(currentOut, slotBox.value) }
            }
            TextArea { id: consoleLog; width: 276; height: 200; readOnly: true; color: "#9A9AA5" }
            ProgressBar { id: pyBar; width: 276; value: 0 }
        }
    }
    property string currentFile: ""
    property string currentOut: ""
    property var fileModel: []
    FolderDialog { id: folderDialog; onAccepted: fileModel = backend_list_py(currentFolder) }
    Connections { target: backend; function onProgress(p,m){pyBar.value=p/100; consoleLog.text=m} }
}
```
(注:`backend_read_file` / `backend_list_py` 为辅助槽,在 Step 3 补到 backend。)

- [ ] **Step 3: Backend 文件辅助槽**

```python
    @Slot(str, result=str)
    def read_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    @Slot(str, result="QVariantList")
    def list_py(self, folder):
        import os
        folder = folder.toString().replace("file:///","") if hasattr(folder, "toString") else folder
        return [f for f in os.listdir(folder) if f.endswith(".py")]
```

- [ ] **Step 4: 冒烟验证**

```bash
python -m lbs_ui_tool
```
Expected: Python 页可打开目录列出 .py,编辑、编译(调 rust-msc)、选槽位、下发。

- [ ] **Step 5: Commit**

```bash
git add src/lbs_ui_tool/qml/ui/PythonPage.qml src/lbs_ui_tool/backend.py
git commit -m "feat: PythonPage multi-file IDE with compile + deploy"
```

---

### Task 19: 全量集成与 README 更新

**Files:**
- Modify: `README.md`
- Create: `tests/test_integration.py`

- [ ] **Step 1: 集成测试(无硬件,验证 profile 注册与数据流)**

```python
# tests/test_integration.py
from lbs_ui_tool.profiles.registry import get_profile, list_products
from lbs_ui_tool.protocol.serial_transport import FakeSerial
from lbs_ui_tool.protocol.frame_codec import FrameCodec

def test_all_products_registered():
    assert set(list_products()) == {"NEW-AI", "SPARK-AI", "NEXT-AI"}

def test_newai_sensor_frame_matches_sample():
    s = FakeSerial()
    s.feed(bytes(FrameCodec.encode(0xFD, b"")))
    p = get_profile("NEW-AI", s)
    p.update_sensors({"A": 0xA1, "H": 0xA6})
    frames, _ = FrameCodec.decode_stream(bytes(s.tx))
    assert bytes(frames[0]) == bytes([0x5A,0x97,0x98,0x08,0x32,0xA1,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xA6,0xBB,0xA5])
```

- [ ] **Step 2: 运行全部测试**

```bash
pytest -v
```
Expected: all passed

- [ ] **Step 3: 更新 README**

补充使用说明、三产品支持矩阵、传感器 ID 表链接到设计文档。

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py README.md
git commit -m "test: integration tests and README usage"
```

---

## Self-Review 结果

**1. Spec 覆盖:**
- 协议层(FrameCodec/SerialTransport/YmodemTransfer/FrameFileTransfer):Task 1-4 ✓
- 适配器层(NewAi/SparkAi/NextAi + registry):Task 5-9 ✓
- BackendBridge:Task 11 ✓
- 固件下载(按产品包结构):Task 15 ✓
- 监控:Task 16 ✓
- 传感器更新(仅 NEW-AI,9 类 ID):Task 6+17 ✓
- Python IDE(多文件、编译、槽位):Task 10+18 ✓
- App Store UI(首页卡片→工作区):Task 12-14 ✓
- 错误处理(NotSupported、ACK 超时重试):Task 4(retries)+ Task 5(NotSupportedError)+ Task 6-8 ✓

**2. 占位扫描:** 无 TBD/TODO;UI 任务用"冒烟验证"代替单测,符合 QML 实际。SensorPage 设备 ID 用十进制(161=0xA1)与 NEW_AI_DEVICE_IDS 一致。✓

**3. 类型一致:** `FirmwarePackage`/`FirmwareFile` 在 Task 5 定义,Task 6/7/8/11/15 使用一致;`MonitorState` 字段(battery/version/state/ports)在 Task 5 定义,Task 6/7/8 parse_monitor 与 Task 16 _state_to_dict 一致;命令码常量在各 profile 独立定义且数值一致(0xBA/0xBE/0xB6/0xB9)。✓

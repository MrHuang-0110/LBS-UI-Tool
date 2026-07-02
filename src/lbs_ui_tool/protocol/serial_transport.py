"""串口封装。真实环境用 pyserial,测试用 FakeSerial。"""
from typing import Callable, Optional

import serial.tools.list_ports


class FakeSerial:
    """测试用假串口(回环)。write 同时进 tx(供断言)与 rx(供 read 回环),
    feed 灌 rx,read 从 rx 取,in_waiting 返回 rx 长度。"""

    def __init__(self):
        self.tx = bytearray()
        self._rx = bytearray()

    def feed(self, data: bytes) -> None:
        self._rx.extend(data)

    def write(self, data: bytes) -> int:
        self.tx.extend(data)
        self._rx.extend(data)  # 回环:使 write 后可 read 回相同数据
        return len(data)

    def read(self, n: int) -> bytes:
        chunk = bytes(self._rx[:n])
        del self._rx[:n]
        return chunk

    def in_waiting(self) -> int:
        return len(self._rx)

    def close(self) -> None:
        pass


class SerialTransport:
    def __init__(self, serial, on_data: Optional[Callable[[bytes], None]] = None):
        self._serial = serial
        self._on_data = on_data

    @staticmethod
    def list_ports() -> list[dict]:
        """返回端口列表,每项 {device, description}。
        device 用于 pyserial.Serial 打开(如 'COM3');
        description 是驱动上报的可读名(如 'LBS Serial (COM3)')。"""
        return [
            {"device": p.device, "description": p.description or p.device}
            for p in serial.tools.list_ports.comports()
        ]

    def write(self, data: bytes) -> int:
        return self._serial.write(data)

    def read_once(self) -> bytes:
        # in_waiting 可能是方法(FakeSerial)也可能是属性(pyserial)。
        w = getattr(self._serial, "in_waiting", 0)
        n = w() if callable(w) else w
        if n <= 0:
            return b""
        data = self._serial.read(n)
        if data and self._on_data:
            self._on_data(data)
        return data

    def close(self) -> None:
        self._serial.close()

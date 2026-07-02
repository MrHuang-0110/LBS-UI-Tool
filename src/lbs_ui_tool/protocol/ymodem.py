"""YMODEM 发送端实现(NEXT-AI 固件/Python 下发用)。

标准 YMODEM 发送流程:
    'C'(握手) -> SOH 文件名块(filename\\0size,128B 补零) -> ACK -> 'C'(继续)
    -> 逐块 SOH(128)/STX(1024) 数据块 -> 每块 ACK
    -> SOH 空结束块(seq=0) -> ACK -> EOT -> ACK

CRC-16-XMODEM:多项式 0x1021,初始 0。

回环处理:测试用 FakeSerial 把 host write 的字节同时回环进 _rx,host 写出的
数据块(SOH/STX/EOT/payload/CRC)不是设备响应,会被 _read_byte 跳过,只返回
设备响应字节('C'/ACK/NAK/CAN),避免等待 ACK 时误读回环的数据块字节。
"""
import time
from typing import Callable, Optional

SOH = 0x01
STX = 0x02
EOT = 0x04
ACK = 0x06
NAK = 0x15
CAN = 0x18
C = 0x43

# 设备可能发回的响应字节;其余字节视为回环噪声,读取时跳过。
_RESPONSE_BYTES = frozenset({C, ACK, NAK, CAN})


def crc16_xmodem(data: bytes) -> int:
    """CRC-16-XMODEM:多项式 0x1021,初始 0。已知 "123456789" -> 0x31C1。"""
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
    """YMODEM 发送端。block_size=1024 走 STX(USB),128 走 SOH(蓝牙)。"""

    def __init__(self, serial, block_size: int = 1024, timeout: float = 1.0):
        self._s = serial
        self.block_size = block_size
        self.timeout = timeout

    def _read_byte(self) -> Optional[int]:
        """读一个设备响应字节('C'/ACK/NAK/CAN),跳过回环的数据块字节。

        FakeSerial 把 host write 的字节回环进 _rx;host 写出的数据块(mark 为
        SOH/STX/EOT,payload、CRC)不是设备响应,_read_byte 跳过这些字节,只
        返回 YMODEM 响应字节,确保等待 ACK 时不被自己刚写出的块前导字节干扰。
        超时返回 None。
        """
        deadline = time.monotonic() + self.timeout
        while True:
            b = self._s.read(1)
            if b:
                byte = b[0]
                if byte in _RESPONSE_BYTES:
                    return byte
                # 非响应字节(回环的数据块字节),跳过继续读
                continue
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.001)

    def _wait_c(self) -> bool:
        """等待设备发 'C'(开始或进入数据阶段)。超时返回 False。"""
        while True:
            byte = self._read_byte()
            if byte is None:
                return False
            if byte == C:
                return True
            # 其他响应(如乱序 ACK)容忍,继续等 'C'

    def _send_block(self, seq: int, payload: bytes) -> bool:
        """发一个数据块并等 ACK。payload 不足 block_size 时补零。"""
        mark = STX if self.block_size == 1024 else SOH
        if len(payload) < self.block_size:
            payload = payload + b"\x00" * (self.block_size - len(payload))
        crc = crc16_xmodem(payload)
        block = (
            bytes([mark, seq & 0xFF, (~seq) & 0xFF])
            + payload
            + bytes([crc >> 8, crc & 0xFF])
        )
        self._s.write(block)
        return self._read_byte() == ACK

    def send(self, filename: str, data: bytes,
             progress_cb: Optional[Callable[[int, int], None]] = None) -> bool:
        """发送一个文件。progress_cb(sent, total) 每个数据块后回调。成功返回 True。"""
        if not self._wait_c():
            return False
        # 文件名块: filename\0size,补零到 128 字节
        name_block = filename.encode() + b"\x00" + str(len(data)).encode()
        name_block += b"\x00" * (128 - len(name_block))
        crc = crc16_xmodem(name_block)
        self._s.write(
            bytes([SOH, 0x00, 0xFF])
            + name_block
            + bytes([crc >> 8, crc & 0xFF])
        )
        if self._read_byte() != ACK:
            return False
        if self._read_byte() != C:
            return False
        # 数据块
        seq = 1
        total = len(data)
        for off in range(0, total, self.block_size):
            chunk = data[off:off + self.block_size]
            if not self._send_block(seq, chunk):
                return False
            if progress_cb:
                progress_cb(off + len(chunk), total)
            seq += 1
        # 空结束块
        if not self._send_block(0, b""):
            return False
        # EOT
        self._s.write(bytes([EOT]))
        return self._read_byte() == ACK

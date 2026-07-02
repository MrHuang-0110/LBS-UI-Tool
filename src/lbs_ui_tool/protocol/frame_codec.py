"""_AGREEMENT 帧编解码。

帧格式: ``0x5A | 0x97 | 0x98 | len(1B) | index(1B) | data[len] | crc(1B) | 0xA5``

字节位置:
    0       HEAD (0x5A)
    1       SID  (0x97)
    2       OID  (0x98)
    3       len  (data 字节数)
    4       index
    5 .. 5+len-1   data
    5+len   crc   = 前面所有字节累加和 & 0xFF
    6+len   TAIL (0xA5)

整帧长度 = 7 + len。
"""
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
        prefix = bytes([HEAD, SID, OID, len(self.data), self.index]) + self.data
        return prefix + bytes([FrameCodec.crc(prefix), TAIL])


class FrameCodec:
    @staticmethod
    def crc(prefix: bytes) -> int:
        return sum(prefix) & 0xFF

    @staticmethod
    def encode(index: int, data: bytes) -> Frame:
        if len(data) > MAX_DATA:
            raise ValueError(f"data too long: {len(data)} > {MAX_DATA}")
        return Frame(index=index, data=bytes(data))

    @staticmethod
    def decode_one(buf: bytes):
        """尝试从 buf 起始解一帧。

        返回 (Frame, consumed) 或 None(数据不足 / 校验失败)。
        """
        if len(buf) < 7:
            return None
        if buf[0] != HEAD:
            return None
        length = buf[3]
        total = 7 + length
        if len(buf) < total:
            return None
        if buf[6 + length] != TAIL:
            return None
        prefix = buf[:5 + length]
        if FrameCodec.crc(prefix) != buf[5 + length]:
            return None
        frame = Frame(index=buf[4], data=bytes(buf[5:5 + length]))
        return frame, total

    @staticmethod
    def decode_stream(buf: bytes):
        """从流中解出尽可能多的帧,跳过非帧头字节。

        返回 (frames, leftover)。遇到帧头但数据不足或校验失败时,保留余量。
        """
        frames = []
        i = 0
        while i < len(buf):
            if buf[i] != HEAD:
                i += 1
                continue
            res = FrameCodec.decode_one(buf[i:])
            if res is None:
                break
            frame, consumed = res
            frames.append(frame)
            i += consumed
        return frames, buf[i:]

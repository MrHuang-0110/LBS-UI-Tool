"""自定义帧文件传输(NEW-AI / SPARK-AI 用)。

流程: 建文件(partition_cmd 携带文件名) -> 0xAA 分块 -> 0xBB 结束。
设备对建文件、每个数据块、结束帧分别回一个 index=0xFD 的 ACK 帧。

``_wait_ack`` 只认 index==0xFD 的帧作为 ACK,跳过 _rx 里 host 自己 write 出去的
_AGREEMENT 帧(0xDA/0xAA/0xBB)。这一过滤对 FakeSerial(回环会把 host 字节灌回
_rx)和真机(host 字节不会回读)都正确。
"""
from typing import Callable, Optional

from lbs_ui_tool.protocol.frame_codec import FrameCodec
from lbs_ui_tool.protocol.serial_transport import SerialTransport

CMD_DATA = 0xAA
CMD_END = 0xBB
ACK = 0xFD

# _wait_ack 单次调用的读循环上限(避免无 ACK 时无限阻塞)。
_WAIT_ACK_MAX_ITERS = 200


class FrameFileTransfer:
    def __init__(self, transport: SerialTransport, retries: int = 3):
        self._t = transport
        self.retries = retries
        # 跨 _wait_ack 调用的持久缓冲:保留尚未解析的半帧,以及已被 decode_stream
        # 解出但因未命中 ACK 而需要留待下次的整帧(重新编码回字节)。
        self._buf = bytearray()

    def _wait_ack(self) -> bool:
        """循环读取并解帧,直到出现 index==0xFD 的帧。

        回环的 host 帧(0xDA/0xAA/0xBB)会被跳过;命中 0xFD 后,缓冲中排在 ACK
        之后的整帧(如下一个 0xFD)重新编码回 ``self._buf``,供下一次 _wait_ack 使用。
        """
        for _ in range(_WAIT_ACK_MAX_ITERS):
            frames, leftover = FrameCodec.decode_stream(bytes(self._buf))
            self._buf = bytearray(leftover)
            for i, frame in enumerate(frames):
                if frame.index == ACK:
                    # 排在 ACK 之后的整帧(尚未消费)重新放回缓冲,保留给下次 _wait_ack。
                    tail = b"".join(bytes(f) for f in frames[i + 1:]) + leftover
                    self._buf = bytearray(tail)
                    return True
                # 非 ACK(回环的 host 帧 0xDA/0xAA/0xBB):丢弃,继续找 0xFD。
            # 当前缓冲里没有完整 ACK;再从串口读一段。
            self._buf += self._t.read_once()
        return False

    def send(self, partition_cmd: int, filename: str, data: bytes,
             block_size: int = 128,
             progress_cb: Optional[Callable[[int], None]] = None) -> bool:
        total = len(data)
        # 1. 建文件: partition_cmd 携带文件名。
        self._t.write(bytes(FrameCodec.encode(partition_cmd, filename.encode())))
        if not self._wait_ack():
            return False
        # 2. 分块发送,每块等 0xFD ACK,失败重试 retries 次。
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
        # 3. 结束帧 + ACK。
        self._t.write(bytes(FrameCodec.encode(CMD_END, b"")))
        if not self._wait_ack():
            return False
        if progress_cb:
            progress_cb(100)
        return True

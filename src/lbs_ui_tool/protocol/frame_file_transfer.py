"""自定义帧文件传输(NEW-AI / SPARK-AI 用)。

流程(按参考实现 SerialDownloader5A.send_file):
建文件(partition_cmd 携带文件名 GBK 编码) -> 数据块 248/块,
除最后一块 CMD=0xBB 外其余 CMD=0xAA(没有独立结束帧)。
设备对文件名帧、每个数据块分别回一个 index=0xFD 的 ACK 帧。

``_wait_ack`` 只认 index==0xFD 的帧作为 ACK,跳过 _rx 里 host 自己 write 出去的
_AGREEMENT 帧(0xDA/0xAA/0xBB)。这一过滤对 FakeSerial(回环会把 host 字节灌回
_rx)和真机(host 字节不会回读)都正确。
"""
import time
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
             block_size: int = 248,
             progress_cb: Optional[Callable[[int], None]] = None) -> bool:
        """按参考实现 SerialDownloader5A.send_file 发送单个文件。

        1. 文件名帧: CMD=partition_cmd(0xDA/0xDB/0xDC/0xDD/0xEC),data=文件名 GBK 编码
        2. 等 0xFD ACK
        3. sleep 0.05
        4. 数据块 block_size(默认 248)/块,除最后一块 CMD=0xBB 外其余 CMD=0xAA
        5. 每块等 0xFD ACK
        """
        # 1. 文件名帧: partition_cmd 携带文件名(GBK 编码,fallback UTF-8)。
        try:
            name_bytes = filename.encode("gbk")
        except UnicodeEncodeError:
            name_bytes = filename.encode("utf-8")
        self._t.write(bytes(FrameCodec.encode(partition_cmd, name_bytes)))
        if not self._wait_ack():
            return False
        time.sleep(0.05)

        total = len(data)
        if total == 0:
            # 参考实现 send_file 的 while sent<total 循环在 total=0 时直接跳过;
            # 文件名 ACK 后即视为完成。
            if progress_cb:
                progress_cb(100)
            return True

        # 2. 数据块: 最后一块 CMD=0xBB,其余 CMD=0xAA,每块等 ACK 并按 retries 重试。
        sent = 0
        while sent < total:
            chunk = data[sent:sent + block_size]
            is_last = (sent + len(chunk) >= total)
            cmd = CMD_END if is_last else CMD_DATA
            ok = False
            for _ in range(self.retries):
                self._t.write(bytes(FrameCodec.encode(cmd, chunk)))
                if self._wait_ack():
                    ok = True
                    break
            if not ok:
                return False
            sent += len(chunk)
            if progress_cb:
                progress_cb(int(sent * 100 / total))
        return True

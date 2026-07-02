"""FrameFileTransfer 单测(自定义帧文件传输,NEW-AI/SPARK 用)。

设备对建文件/每块/结束帧分别回一个 index=0xFD 的 ACK 帧。
FakeSerial 有回环:host write 的字节同时进 tx 与 _rx,因此 _wait_ack 在
读取 _rx 时会先遇到 host 自己发出的 0xDA/0xAA/0xBB 帧——必须跳过它们,
只认 index==0xFD 的帧作为 ACK(对真机也正确:真机不会回读 host 字节)。
"""
from lbs_ui_tool.protocol.frame_file_transfer import FrameFileTransfer
from lbs_ui_tool.protocol.serial_transport import FakeSerial, SerialTransport
from lbs_ui_tool.protocol.frame_codec import FrameCodec


def _ack_device_responses(n_blocks: int) -> bytes:
    """构造设备 ACK: 建文件 + n_blocks 数据块 + 结束,共 n_blocks+2 个 0xFD 帧。"""
    one = bytes(FrameCodec.encode(0xFD, b""))
    return one * (n_blocks + 2)


def _make_transfer():
    """FakeSerial 经 SerialTransport 包装后交给 FrameFileTransfer。

    SerialTransport 提供 read_once/write;FakeSerial 提供回环 _rx 与可断言的 tx。
    """
    s = FakeSerial()
    t = FrameFileTransfer(SerialTransport(s))
    return s, t


def test_send_file_sends_start_blocks_end():
    s, t = _make_transfer()
    data = b"\x01" * 300  # 128 + 128 + 44 => 3 块
    s.feed(_ack_device_responses(3))  # 5 个 0xFD 帧

    ok = t.send(partition_cmd=0xDA, filename="app.bin", data=data, block_size=128)

    assert ok is True
    frames, leftover = FrameCodec.decode_stream(bytes(s.tx))
    assert leftover == b""
    indexes = [f.index for f in frames]
    assert indexes[0] == 0xDA           # 建文件
    assert indexes.count(0xAA) == 3     # 3 个数据块
    assert indexes[-1] == 0xBB          # 结束


def test_progress_callback():
    s, t = _make_transfer()
    data = b"\x01" * 256  # 2 块
    s.feed(_ack_device_responses(2))  # 4 个 0xFD 帧

    seen = []
    ok = t.send(0xDA, "app.bin", data, block_size=128, progress_cb=seen.append)

    assert ok is True
    assert seen  # 至少回调过
    assert seen[-1] == 100

"""FrameFileTransfer 单测(自定义帧文件传输,NEW-AI/SPARK 用)。

按参考实现 SerialDownloader5A.send_file:
- 文件名帧 CMD = partition_cmd,data = 文件名 GBK 编码
- 等 0xFD ACK,sleep 0.05
- 数据块 248/块,除最后一块 CMD=0xBB,其余 CMD=0xAA,每块等 0xFD ACK
- 没有独立的结束帧:最后一块直接用 0xBB

设备对文件名帧、每个数据块分别回一个 index=0xFD 的 ACK 帧。
FakeSerial 有回环:host write 的字节同时进 tx 与 _rx,因此 _wait_ack 在
读取 _rx 时会先遇到 host 自己发出的 0xDA/0xAA/0xBB 帧——必须跳过它们,
只认 index==0xFD 的帧作为 ACK(对真机也正确:真机不会回读 host 字节)。
"""
from lbs_ui_tool.protocol.frame_file_transfer import FrameFileTransfer
from lbs_ui_tool.protocol.serial_transport import FakeSerial, SerialTransport
from lbs_ui_tool.protocol.frame_codec import FrameCodec


def _ack_device_responses(n_blocks: int) -> bytes:
    """构造设备 ACK: 文件名帧 + n_blocks 数据块,共 n_blocks+1 个 0xFD 帧。

    参考实现没有独立结束帧,最后一块 CMD=0xBB,故 ACK 总数 = 1(文件名) + 块数。
    """
    one = bytes(FrameCodec.encode(0xFD, b""))
    return one * (n_blocks + 1)


def _make_transfer():
    """FakeSerial 经 SerialTransport 包装后交给 FrameFileTransfer。"""
    s = FakeSerial()
    t = FrameFileTransfer(SerialTransport(s))
    return s, t


def test_send_file_last_block_uses_end_cmd():
    s, t = _make_transfer()
    data = b"\x01" * 300  # block_size=128 => 128 + 128 + 44 => 3 块
    s.feed(_ack_device_responses(3))  # 4 个 0xFD 帧(文件名 + 3 块)

    ok = t.send(partition_cmd=0xDA, filename="app.bin", data=data, block_size=128)

    assert ok is True
    frames, leftover = FrameCodec.decode_stream(bytes(s.tx))
    assert leftover == b""
    indexes = [f.index for f in frames]
    assert indexes[0] == 0xDA           # 文件名帧
    assert indexes.count(0xAA) == 2     # 前两块中间块
    assert indexes.count(0xBB) == 1     # 最后一块用结束命令码
    assert indexes[-1] == 0xBB          # 最后发出的就是 0xBB 块(无独立结束帧)


def test_default_block_size_is_248():
    s, t = _make_transfer()
    data = b"\x02" * 500  # 248 + 248 + 4 => 3 块
    s.feed(_ack_device_responses(3))

    ok = t.send(0xDA, "app.bin", data)  # 不传 block_size,默认 248

    assert ok is True
    frames, _ = FrameCodec.decode_stream(bytes(s.tx))
    data_frames = [f for f in frames if f.index in (0xAA, 0xBB)]
    assert len(data_frames) == 3
    assert len(data_frames[0].data) == 248
    assert len(data_frames[1].data) == 248
    assert len(data_frames[2].data) == 4
    assert data_frames[2].index == 0xBB


def test_filename_encoded_gbk():
    s, t = _make_transfer()
    data = b"\x01" * 10
    s.feed(_ack_device_responses(1))  # 1 块

    ok = t.send(0xDA, "音乐.bin", data, block_size=128)

    assert ok is True
    frames, _ = FrameCodec.decode_stream(bytes(s.tx))
    assert frames[0].index == 0xDA
    assert frames[0].data == "音乐.bin".encode("gbk")


def test_progress_callback():
    s, t = _make_transfer()
    data = b"\x01" * 256  # block_size=128 => 2 块
    s.feed(_ack_device_responses(2))  # 3 个 0xFD 帧

    seen = []
    ok = t.send(0xDA, "app.bin", data, block_size=128, progress_cb=seen.append)

    assert ok is True
    assert seen  # 至少回调过
    assert seen[-1] == 100

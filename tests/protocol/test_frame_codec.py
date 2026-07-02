"""FrameCodec (_AGREEMENT 帧编解码) 单测。

帧格式: 0x5A | 0x97 | 0x98 | len(1B) | index(1B) | data[len] | crc(1B) | 0xA5
crc = 前面所有字节累加和 & 0xFF

注: 计划文档 Step 1 里 test_encode_minimal_frame / test_crc_is_sum_low_byte
硬编码的 crc=0x49 与 test_decode_valid_frame 硬编码的 crc=0x3F 是算术笔误。
以用户给的传感器样例(5A 97 98 08 32 FF*8 BB A5)为基准,crc 规则确认为
sum & 0xFF,该规则下:
  - [5A 97 98 00 BA]      -> 0x43 (非 0x49)
  - [5A 97 98 02 AA 01 02] -> 0x38 (非 0x3F)
此处按正确值断言。
"""
from lbs_ui_tool.protocol.frame_codec import FrameCodec, Frame


def test_encode_minimal_frame():
    frame = FrameCodec.encode(index=0xBA, data=b"")
    # 5A 97 98 00 BA crc A5 ; crc=(5A+97+98+00+BA)&0xFF = 0x43
    assert bytes(frame) == bytes([0x5A, 0x97, 0x98, 0x00, 0xBA, 0x43, 0xA5])


def test_encode_with_data():
    # 用户给的传感器样例: 5A 97 98 08 32 FF*8 BB A5
    frame = FrameCodec.encode(index=0x32, data=b"\xFF" * 8)
    assert bytes(frame) == bytes([0x5A, 0x97, 0x98, 0x08, 0x32] + [0xFF] * 8 + [0xBB, 0xA5])


def test_crc_is_sum_low_byte():
    assert FrameCodec.crc(bytes([0x5A, 0x97, 0x98, 0x00, 0xBA])) == 0x43


def test_decode_valid_frame():
    raw = bytes([0x5A, 0x97, 0x98, 0x02, 0xAA, 0x01, 0x02, 0x38, 0xA5])
    # decode_one 返回 (Frame, consumed);计划原文按 Frame 直接取属性,与返回签名矛盾,此处解包。
    result = FrameCodec.decode_one(raw)
    assert result is not None
    frame, consumed = result
    assert frame.index == 0xAA
    assert frame.data == b"\x01\x02"
    assert consumed == 9


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

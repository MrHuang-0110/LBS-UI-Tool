"""端到端集成测试(无硬件)。

验证:产品注册表完整、NEW-AI 传感器 0x32 帧的字节级 wire 格式。
用 FakeSerial 代替真实串口,跑通 profile -> transport -> frame_codec 全链路。
"""
from lbs_ui_tool.profiles.registry import get_profile, list_products
from lbs_ui_tool.protocol.serial_transport import FakeSerial, SerialTransport
from lbs_ui_tool.protocol.frame_codec import FrameCodec


def test_all_products_registered():
    """三款产品必须在注册表中(任一缺失会让首页卡片点进去后无法连接)。"""
    assert set(list_products()) == {"NEW-AI", "SPARK-AI", "NEXT-AI"}


def test_newai_sensor_frame_matches_sample():
    """NEW-AI update_sensors 写出的 0x32 帧必须与设备侧期望的 wire 格式一致。

    端口 A=大电机(0xA1)、H=小电机(0xA6),其余 6 端口保持 0xFF。
    帧 = 5A 97 98 08 32 [A1 FF FF FF FF FF FF A6] crc A5,
    其中 crc = (前面所有字节累加和) & 0xFF = 0x04。

    注:计划文档里此样例的 crc 误写为 0xBB(那是全 0xFF 数据的 crc),
    实际 crc 算法为 sum & 0xFF,对 A1/A6 数据计算得 0x04。此处断言真实值。
    """
    s = FakeSerial()
    p = get_profile("NEW-AI", SerialTransport(s))
    p.update_sensors({"A": 0xA1, "H": 0xA6})
    frames, _ = FrameCodec.decode_stream(bytes(s.tx))
    assert len(frames) == 1
    assert frames[0].index == 0x32
    expected = bytes([0x5A, 0x97, 0x98, 0x08, 0x32,
                      0xA1, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA6,
                      0x04, 0xA5])
    assert bytes(frames[0]) == expected

"""NewAiProfile 单测。

构造接收 SerialTransport(不是裸 FakeSerial):FrameFileTransfer 内部调
transport.read_once(),而 FakeSerial 没有该方法。回环特性:FakeSerial.write
同时进 tx(供断言)与 _rx(供 read 回环);_wait_ack 只认 0xFD 帧作为 ACK,
跳过回环的 host 帧(0xDA/0xAA/0xBB)。
"""
import json

from lbs_ui_tool.profiles.new_ai import NewAiProfile, NEW_AI_DEVICE_IDS
from lbs_ui_tool.protocol.serial_transport import FakeSerial, SerialTransport
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
    fake = FakeSerial()
    p = NewAiProfile(SerialTransport(fake))
    tpl = p.firmware_template()
    parts = {f.partition for f in tpl.files}
    assert parts == {"app", "boot", "config", "music", "version"}


def test_update_sensors_builds_0x32_frame():
    # update_sensors 只 write 不 _wait_ack,故无需 feed 设备 ACK;
    # FakeSerial 回环会把 host write 的 0x32 帧灌回 _rx,但 update_sensors 不读,无影响。
    fake = FakeSerial()
    p = NewAiProfile(SerialTransport(fake))
    # A 端口=大电机(0xA1), H 端口=小电机(0xA6), 其余 KEEP=0xFF
    p.update_sensors({"A": 0xA1, "H": 0xA6})
    frames, leftover = FrameCodec.decode_stream(bytes(fake.tx))
    assert leftover == b""
    assert len(frames) == 1
    assert frames[0].index == 0x32
    data = frames[0].data
    assert data[0] == 0xA1
    assert data[1] == 0xFF
    assert data[7] == 0xA6
    assert len(data) == 8


def test_parse_monitor_normalizes():
    fake = FakeSerial()
    p = NewAiProfile(SerialTransport(fake))
    payload = json.dumps({
        "deviceList": [
            {"port": 0, "big_motor": {"circly": "1.00", "speed": "50", "angle": "90"}}
        ],
        "bat": "95.20",
        "version": 100,
        "heap": "45",
        "NewAiState": "run",
    }).encode()
    state = p.parse_monitor(payload)
    assert state.battery == 95.2
    assert state.version == "100"
    assert state.state == "run"
    assert 0 in state.ports


def test_enter_bootloader_sends_reset_fwlib_frame():
    """0x6F + b"RESET_FWLIB" 帧,CRC 累加和低 8 位。"""
    from lbs_ui_tool.protocol.serial_transport import FakeSerial, SerialTransport
    from lbs_ui_tool.protocol.frame_codec import FrameCodec
    fake = FakeSerial()
    p = NewAiProfile(SerialTransport(fake))
    p.enter_bootloader()
    frames, _ = FrameCodec.decode_stream(bytes(fake.tx))
    assert len(frames) == 1
    assert frames[0].index == 0x6F
    assert frames[0].data == b"RESET_FWLIB"
    # 完整字节验证(CRC = 前缀累加和 & 0xFF = 0x559 & 0xFF = 0x59)
    assert bytes(frames[0]) == bytes.fromhex("5A9798 0B 6F 52455345545F46574C4942 59 A5".replace(" ", ""))


def test_new_ai_needs_bootloader_switch():
    from lbs_ui_tool.protocol.serial_transport import FakeSerial, SerialTransport
    p = NewAiProfile(SerialTransport(FakeSerial()))
    assert p.needs_bootloader_switch() is True

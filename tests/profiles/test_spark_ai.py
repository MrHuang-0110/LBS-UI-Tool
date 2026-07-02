"""SparkAiProfile 单测。

构造接收 SerialTransport(不是裸 FakeSerial):FrameFileTransfer 内部调
transport.read_once(),而 FakeSerial 没有该方法。回环特性:FakeSerial.write
同时进 tx(供断言)与 _rx(供 read 回环);_wait_ack 只认 0xFD 帧作为 ACK,
跳过回环的 host 帧(0xDA/0xAA/0xBB)。

SPARK-AI 不支持传感器更新,基类 update_sensors 抛 NotSupportedError。
"""
import json

import pytest

from lbs_ui_tool.profiles.base import NotSupportedError
from lbs_ui_tool.profiles.spark_ai import SparkAiProfile
from lbs_ui_tool.protocol.serial_transport import FakeSerial, SerialTransport


def test_firmware_template_app_version():
    fake = FakeSerial()
    p = SparkAiProfile(SerialTransport(fake))
    parts = {f.partition for f in p.firmware_template().files}
    assert parts == {"app", "version"}


def test_update_sensors_not_supported():
    fake = FakeSerial()
    p = SparkAiProfile(SerialTransport(fake))
    with pytest.raises(NotSupportedError):
        p.update_sensors({})


def test_parse_monitor_uses_willaistate():
    fake = FakeSerial()
    p = SparkAiProfile(SerialTransport(fake))
    payload = json.dumps({
        "deviceList": [{"port": 0, "touch": {"state": 0}}],
        "adc": {"bat": "85%"},
        "version": 100,
        "heap": "45",
        "WillAiState": "run",
    }).encode()
    state = p.parse_monitor(payload)
    assert state.state == "run"
    assert state.battery == 85.0


def test_spark_ai_does_not_need_bootloader_switch():
    from lbs_ui_tool.protocol.serial_transport import FakeSerial, SerialTransport
    p = SparkAiProfile(SerialTransport(FakeSerial()))
    assert p.needs_bootloader_switch() is False

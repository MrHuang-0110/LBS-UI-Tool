"""NextAiProfile 单测。

NEXT-AI 走 YMODEM 单 bin 升级,不支持传感器更新(基类 update_sensors 抛
NotSupportedError)。构造接收 SerialTransport(包裹 FakeSerial);本组 3 个
用例只覆盖模板/不支持/解析,YMODEM 发送路径由 test_ymodem.py 覆盖。
"""
import json

import pytest

from lbs_ui_tool.profiles.base import NotSupportedError
from lbs_ui_tool.profiles.next_ai import NextAiProfile
from lbs_ui_tool.protocol.serial_transport import FakeSerial, SerialTransport


def test_firmware_template_single_bin():
    fake = FakeSerial()
    p = NextAiProfile(SerialTransport(fake))
    files = p.firmware_template().files
    assert len(files) == 1
    assert files[0].partition == ""


def test_update_sensors_not_supported():
    fake = FakeSerial()
    with pytest.raises(NotSupportedError):
        NextAiProfile(SerialTransport(fake)).update_sensors({})


def test_parse_monitor_basic():
    fake = FakeSerial()
    p = NextAiProfile(SerialTransport(fake))
    payload = json.dumps({"bat": "80", "version": 50, "state": "idle"}).encode()
    st = p.parse_monitor(payload)
    assert st.battery == 80.0
    assert st.version == "50"

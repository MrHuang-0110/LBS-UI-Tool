"""Profile 注册表测试。"""
import pytest

from lbs_ui_tool.profiles.registry import get_profile, list_products
from lbs_ui_tool.profiles.new_ai import NewAiProfile
from lbs_ui_tool.profiles.spark_ai import SparkAiProfile
from lbs_ui_tool.profiles.next_ai import NextAiProfile
from lbs_ui_tool.protocol.serial_transport import SerialTransport, FakeSerial


def test_list_products():
    assert set(list_products()) == {"NEW-AI", "SPARK-AI", "NEXT-AI"}


def test_get_profile_by_name():
    s = SerialTransport(FakeSerial())
    assert isinstance(get_profile("NEW-AI", s), NewAiProfile)
    assert isinstance(get_profile("SPARK-AI", s), SparkAiProfile)
    assert isinstance(get_profile("NEXT-AI", s), NextAiProfile)


def test_unknown_raises():
    with pytest.raises(KeyError):
        get_profile("???", SerialTransport(FakeSerial()))

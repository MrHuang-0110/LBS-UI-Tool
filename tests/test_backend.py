"""BackendBridge 单测 —— 暴露给 QML 的应用层单例。"""
import pytest
from pytestqt.qtbot import QtBot

from lbs_ui_tool.backend import BackendBridge
from lbs_ui_tool.protocol.serial_transport import FakeSerial


def test_list_products(qtbot: QtBot):
    b = BackendBridge()
    assert "NEW-AI" in b.list_products()


def test_list_ports(qtbot: QtBot):
    b = BackendBridge()
    assert isinstance(b.list_ports(), list)


def test_connect_selects_profile(qtbot: QtBot, monkeypatch):
    b = BackendBridge()
    fake = FakeSerial()
    monkeypatch.setattr(b, "_open_serial", lambda port: fake)
    b.connect_device("COM1", "NEW-AI")
    assert b.is_connected
    assert b.profile.name == "NEW-AI"


def test_progress_signal_emitted(qtbot: QtBot, monkeypatch):
    b = BackendBridge()
    fake = FakeSerial()
    monkeypatch.setattr(b, "_open_serial", lambda port: fake)
    b.connect_device("COM1", "SPARK-AI")
    with qtbot.waitSignal(b.progress, timeout=1000) as blocker:
        b.emit_progress(50, "test")
    assert blocker.args[0] == 50

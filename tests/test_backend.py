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


def test_download_firmware_not_connected(qtbot: QtBot):
    """未连接时 download_firmware 应 emit taskFinished(False)。"""
    b = BackendBridge()
    with qtbot.waitSignal(b.taskFinished, timeout=1000) as blocker:
        b.download_firmware([{"partition": "app", "path": "x.bin"}])
    assert blocker.args[0] is False


def test_state_to_dict():
    from lbs_ui_tool.profiles.base import MonitorState
    st = MonitorState(battery=90.0, version="100", state="run", ports={0: {"touch": 1}})
    d = BackendBridge._state_to_dict(st)
    assert d["battery"] == 90.0
    assert d["ports"]["0"] == {"touch": 1}


def test_monitor_poll_parses_frame(qtbot: QtBot, monkeypatch):
    import json
    from lbs_ui_tool.protocol.serial_transport import FakeSerial, SerialTransport
    from lbs_ui_tool.protocol.frame_codec import FrameCodec
    b = BackendBridge()
    fake = FakeSerial()
    monkeypatch.setattr(b, "_open_serial", lambda port: fake)
    b.connect_device("COM1", "NEW-AI")
    payload = json.dumps({"bat": "95", "version": 100, "NewAiState": "run"}).encode()
    fake.feed(bytes(FrameCodec.encode(0x00, payload)))  # index 无所谓,parse_monitor 只看 data
    received = []
    b.monitorState.connect(lambda d: received.append(d))
    b._poll_serial()
    assert received
    assert received[0]["battery"] == 95.0


def test_update_sensors_not_connected(qtbot: QtBot):
    b = BackendBridge()
    with qtbot.waitSignal(b.taskFinished, timeout=1000) as blocker:
        b.update_sensors({"A": 161})
    assert blocker.args[0] == False


def test_update_sensors_emits_frame(qtbot: QtBot, monkeypatch):
    from lbs_ui_tool.protocol.serial_transport import FakeSerial
    from lbs_ui_tool.protocol.frame_codec import FrameCodec
    b = BackendBridge()
    fake = FakeSerial()
    monkeypatch.setattr(b, "_open_serial", lambda port: fake)
    b.connect_device("COM1", "NEW-AI")
    with qtbot.waitSignal(b.taskFinished, timeout=1000) as blocker:
        b.update_sensors({"A": 161, "H": 166})
    assert blocker.args[0] == True
    frames, _ = FrameCodec.decode_stream(bytes(fake.tx))
    assert frames[0].index == 0x32
    assert frames[0].data[0] == 0xA1
    assert frames[0].data[7] == 0xA6


def test_read_file(qtbot: QtBot, tmp_path):
    p = tmp_path / "a.py"
    p.write_text("print('hi')", encoding="utf-8")
    b = BackendBridge()
    assert b.read_file(str(p)) == "print('hi')"


def test_list_py(qtbot: QtBot, tmp_path):
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.txt").write_text("y")
    b = BackendBridge()
    result = b.list_py(str(tmp_path))
    assert "a.py" in result
    assert "b.txt" not in result


def test_compile_python_failure_emits(qtbot: QtBot, monkeypatch):
    import lbs_ui_tool.pika_compiler as pc
    monkeypatch.setattr(
        pc.PikaCompiler, "compile",
        lambda self, src, out=None: (_ for _ in ()).throw(RuntimeError("syntax error")),
    )
    b = BackendBridge()
    with qtbot.waitSignal(b.taskFinished, timeout=2000) as blocker:
        b.compile_python("any.py")
    assert blocker.args[0] == False
    assert "syntax error" in blocker.args[1]


def test_write_file(qtbot: QtBot, tmp_path):
    p = tmp_path / "w.py"
    b = BackendBridge()
    b.write_file(str(p), "hello")
    assert p.read_text(encoding="utf-8") == "hello"

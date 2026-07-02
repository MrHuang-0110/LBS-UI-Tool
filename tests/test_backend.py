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


def test_connect_device_open_failure_emits(qtbot: QtBot, monkeypatch):
    """F1: pyserial 打开失败时,profile 仍为 None,taskFinished(False) 触发,connected 不发。"""
    b = BackendBridge()

    def bad_open(port):
        raise OSError("port busy")

    monkeypatch.setattr(b, "_open_serial", bad_open)
    connected_calls = []
    b.connected.connect(lambda: connected_calls.append(True))
    with qtbot.waitSignal(b.taskFinished, timeout=1000) as blocker:
        b.connect_device("COM99", "NEW-AI")
    assert blocker.args[0] == False
    assert "port busy" in blocker.args[1] or "连接失败" in blocker.args[1]
    assert b.profile is None
    assert connected_calls == []


def test_enable_monitor_not_connected_emits(qtbot: QtBot):
    """F2: 未连接切监控开关,应 emit taskFinished(False, 未连接...)。"""
    b = BackendBridge()
    with qtbot.waitSignal(b.taskFinished, timeout=1000) as blocker:
        b.enable_monitor(True)
    assert blocker.args[0] == False
    assert "未连接" in blocker.args[1]


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


# —— worker 线程(Task 19 收口项 2)——

def test_run_in_worker_runs_task(qtbot: QtBot):
    """_run_in_worker 在后台线程执行 fn;fn 内 emit 的信号经 Qt 队列连接
    回主线程,qtbot.waitSignal 能收到。"""
    b = BackendBridge()
    done = []

    def good():
        done.append(True)
        b.taskFinished.emit(True, "ok")

    with qtbot.waitSignal(b.taskFinished, timeout=2000) as blocker:
        b._run_in_worker(good)
    assert done == [True]
    assert blocker.args[0] is True
    assert blocker.args[1] == "ok"


def test_run_in_worker_emits_on_exception(qtbot: QtBot):
    """fn 抛异常时 _run_in_worker 捕获并 emit taskFinished(False, 错误信息)。"""
    b = BackendBridge()

    def bad():
        raise RuntimeError("boom")

    with qtbot.waitSignal(b.taskFinished, timeout=2000) as blocker:
        b._run_in_worker(bad)
    assert blocker.args[0] is False
    assert "boom" in blocker.args[1]


def test_scan_firmware_dir_slot(qtbot, monkeypatch, tmp_path):
    from lbs_ui_tool.protocol.serial_transport import FakeSerial
    (tmp_path / "app").write_bytes(b"x")
    (tmp_path / "version").write_bytes(b"1")
    b = BackendBridge()
    fake = FakeSerial()
    monkeypatch.setattr(b, "_open_serial", lambda port: fake)
    b.connect_device("COM1", "SPARK-AI")
    result = b.scan_firmware_dir(str(tmp_path))
    assert isinstance(result, list)
    assert {r["partition"] for r in result} == {"app", "version"}
    for r in result:
        assert r["path"].endswith(r["partition"])


def test_scan_firmware_dir_not_connected(qtbot):
    b = BackendBridge()
    assert b.scan_firmware_dir("/some/path") == []


def test_download_firmware_calls_enter_bootloader_for_new_ai(qtbot, monkeypatch, tmp_path):
    """NEW-AI 走 download 前应触发 enter_bootloader 与端口重连流程。"""
    import time as _time
    from lbs_ui_tool.protocol.serial_transport import FakeSerial
    fake = FakeSerial()
    fake.port = "COM_TEST"
    b = BackendBridge()
    monkeypatch.setattr(b, "_open_serial", lambda port: fake)
    b.connect_device("COM_TEST", "NEW-AI")
    # mock:避免真等 2s+5s(长 sleep 只记录不真等)
    orig_sleep = _time.sleep
    monkeypatch.setattr("time.sleep", lambda s: orig_sleep(s) if s < 1.0 else None)
    # mock:profile.download_firmware 不真跑,只标记调用
    called = []
    monkeypatch.setattr(b.profile, "download_firmware", lambda pkg, cb: called.append(True))
    # mock:enter_bootloader 用 spy(直接调用真的实现,只是想验证它被调过)
    enter_calls = []
    orig_enter = b.profile.enter_bootloader
    def spy_enter():
        enter_calls.append(True)
        orig_enter()
    monkeypatch.setattr(b.profile, "enter_bootloader", spy_enter)
    # 触发
    src = tmp_path / "app.bin"
    src.write_bytes(b"x")
    with qtbot.waitSignal(b.taskFinished, timeout=20000) as blocker:
        b.download_firmware([{"partition": "app", "path": str(src)}])
    assert blocker.args[0] is True
    assert enter_calls == [True]
    assert called == [True]


def test_enter_bootloader_and_reconnect_delays_before_return(qtbot, monkeypatch, tmp_path):
    """重连后应有 5s BOOT 就绪等待,再让 download_firmware 开始。

    照搬参考实现 reset_device:关串口 → sleep(2s) → 重试 open → open 成功后 sleep(5s)。
    不做端口消失/重现检测。
    """
    import time as _time
    from lbs_ui_tool.protocol.serial_transport import FakeSerial

    fake = FakeSerial()
    fake.port = "COM_TEST"
    b = BackendBridge()
    monkeypatch.setattr(b, "_open_serial", lambda port: fake)
    b.connect_device("COM_TEST", "NEW-AI")

    # 记录 sleep 调用时长,避免真等 2s+5s(单测要快)
    sleeps = []
    orig_sleep = _time.sleep
    def fake_sleep(sec):
        sleeps.append(sec)
        # 短 sleep 保留真等,长 sleep(>=1s)只记录不真等
        if sec < 1.0:
            orig_sleep(sec)
    monkeypatch.setattr("time.sleep", fake_sleep)

    called = []
    monkeypatch.setattr(b.profile, "download_firmware", lambda pkg, cb: called.append(True))
    monkeypatch.setattr(b.profile, "enter_bootloader", lambda: None)

    src = tmp_path / "app.bin"
    src.write_bytes(b"x")
    with qtbot.waitSignal(b.taskFinished, timeout=20000):
        b.download_firmware([{"partition": "app", "path": str(src)}])

    assert called == [True]
    # 应有一次 2s 重启等待 + 一次 5s BOOT 就绪等待
    assert any(s >= 2.0 for s in sleeps), f"expected 2s reset sleep, got {sleeps}"
    assert any(s >= 5.0 for s in sleeps), f"expected 5s BOOT-ready sleep, got {sleeps}"


def test_download_firmware_skips_bootloader_switch_for_spark(qtbot, monkeypatch, tmp_path):
    """SPARK-AI 不需要两阶段:enter_bootloader 不应被调用。"""
    from lbs_ui_tool.protocol.serial_transport import FakeSerial
    fake = FakeSerial()
    fake.port = "COM_TEST"
    b = BackendBridge()
    monkeypatch.setattr(b, "_open_serial", lambda port: fake)
    b.connect_device("COM_TEST", "SPARK-AI")
    monkeypatch.setattr(b.profile, "download_firmware", lambda pkg, cb: None)
    # SPARK 默认没 enter_bootloader?基类给的 pass 实现,能被 spy 到但不必被调
    enter_calls = []
    monkeypatch.setattr(b.profile, "enter_bootloader", lambda: enter_calls.append(True))
    src = tmp_path / "app.bin"
    src.write_bytes(b"x")
    with qtbot.waitSignal(b.taskFinished, timeout=5000):
        b.download_firmware([{"partition": "app", "path": str(src)}])
    assert enter_calls == []  # SPARK 不需要,不应被调用

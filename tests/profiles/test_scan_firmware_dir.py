"""扫描固件包目录,自动识别各分区文件。"""
import os
import pytest
from lbs_ui_tool.protocol.serial_transport import FakeSerial, SerialTransport
from lbs_ui_tool.profiles.new_ai import NewAiProfile
from lbs_ui_tool.profiles.spark_ai import SparkAiProfile
from lbs_ui_tool.profiles.next_ai import NextAiProfile


def _mk(tp):
    return tp(SerialTransport(FakeSerial()))


def test_new_ai_scan_matches_five_files(tmp_path):
    """NEW-AI: 目录里放 app/boot/config/music/version 五个无后缀文件,
    scan 返回同顺序 5 项,path 全填。"""
    for name in ["app", "boot", "config", "music", "version"]:
        (tmp_path / name).write_bytes(b"x")
    pkg = _mk(NewAiProfile).scan_firmware_dir(str(tmp_path))
    parts = [f.partition for f in pkg.files]
    assert parts == ["app", "boot", "config", "music", "version"]
    for f in pkg.files:
        assert f.path.endswith(f.partition)
        assert os.path.isfile(f.path)


def test_new_ai_scan_missing_optional_leaves_empty(tmp_path):
    """NEW-AI: 只放 app + version,其余分区 path 为空串(可选未提供)。"""
    (tmp_path / "app").write_bytes(b"x")
    (tmp_path / "version").write_bytes(b"1")
    pkg = _mk(NewAiProfile).scan_firmware_dir(str(tmp_path))
    by_part = {f.partition: f for f in pkg.files}
    assert by_part["app"].path.endswith("app")
    assert by_part["version"].path.endswith("version")
    assert by_part["boot"].path == ""
    assert by_part["config"].path == ""
    assert by_part["music"].path == ""


def test_spark_scan_two_files(tmp_path):
    (tmp_path / "app").write_bytes(b"x")
    (tmp_path / "version").write_bytes(b"1")
    pkg = _mk(SparkAiProfile).scan_firmware_dir(str(tmp_path))
    parts = [f.partition for f in pkg.files]
    assert parts == ["app", "version"]
    assert all(f.path for f in pkg.files)


def test_next_scan_picks_bin(tmp_path):
    """NEXT-AI: 目录里任意一个 .bin,取字典序第一个。"""
    (tmp_path / "firmware.bin").write_bytes(b"x")
    (tmp_path / "notes.txt").write_bytes(b"skip")   # 非 .bin 应忽略
    pkg = _mk(NextAiProfile).scan_firmware_dir(str(tmp_path))
    assert len(pkg.files) == 1
    assert pkg.files[0].partition == ""
    assert pkg.files[0].path.endswith("firmware.bin")


def test_next_scan_empty_dir_no_bin(tmp_path):
    pkg = _mk(NextAiProfile).scan_firmware_dir(str(tmp_path))
    assert len(pkg.files) == 1
    assert pkg.files[0].path == ""


def test_scan_missing_dir_returns_empty_paths(tmp_path):
    """目录不存在时,NEW-AI 返回 5 项 path 全空,不抛异常。"""
    missing = str(tmp_path / "not_exist")
    pkg = _mk(NewAiProfile).scan_firmware_dir(missing)
    assert len(pkg.files) == 5
    assert all(f.path == "" for f in pkg.files)

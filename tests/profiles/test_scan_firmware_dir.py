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


def test_new_ai_scan_expands_partition_subdirs(tmp_path):
    """真实结构:分区是子目录,子目录里多个文件应各展开成一个 FirmwareFile,
    共享同一 partition 字段。"""
    import os
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "app.bin").write_bytes(b"1")
    (tmp_path / "app" / "pikaNewAi.bin").write_bytes(b"2")
    (tmp_path / "app" / "motor.bin").write_bytes(b"3")
    (tmp_path / "boot").mkdir()
    (tmp_path / "boot" / "registryApp.txt").write_bytes(b"x")
    (tmp_path / "version").mkdir()
    (tmp_path / "version" / "Version.txt").write_bytes(b"1")
    (tmp_path / "version" / "gray.txt").write_bytes(b"2")
    # config / music 缺失(未提供)

    pkg = _mk(NewAiProfile).scan_firmware_dir(str(tmp_path))

    # 展开后:app(3) + boot(1) + config(占位1) + music(占位1) + version(2) = 8 项
    assert len(pkg.files) == 8

    # 按 partition 分组
    by_part = {}
    for f in pkg.files:
        by_part.setdefault(f.partition, []).append(f)
    assert len(by_part["app"]) == 3
    assert len(by_part["boot"]) == 1
    assert len(by_part["config"]) == 1
    assert by_part["config"][0].path == ""  # 缺失占位
    assert len(by_part["music"]) == 1
    assert by_part["music"][0].path == ""
    assert len(by_part["version"]) == 2

    # 展开的文件名按字母序(确保稳定顺序)
    app_names = sorted(os.path.basename(f.path) for f in by_part["app"])
    assert app_names == ["app.bin", "motor.bin", "pikaNewAi.bin"]


def test_new_ai_scan_partition_subdir_empty(tmp_path):
    """分区子目录存在但空:该分区仍占位一条 path 空。"""
    (tmp_path / "app").mkdir()  # 空目录
    pkg = _mk(NewAiProfile).scan_firmware_dir(str(tmp_path))
    app_entries = [f for f in pkg.files if f.partition == "app"]
    assert len(app_entries) == 1
    assert app_entries[0].path == ""


def test_new_ai_scan_only_lists_files_in_subdir(tmp_path):
    """分区子目录里的子目录不递归下发,只列一级文件。"""
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "a.bin").write_bytes(b"x")
    (tmp_path / "app" / "subdir").mkdir()
    (tmp_path / "app" / "subdir" / "b.bin").write_bytes(b"y")
    pkg = _mk(NewAiProfile).scan_firmware_dir(str(tmp_path))
    app_entries = [f for f in pkg.files if f.partition == "app"]
    # 只有 a.bin,不包含 subdir/b.bin
    assert len(app_entries) == 1
    assert app_entries[0].path.endswith("a.bin")

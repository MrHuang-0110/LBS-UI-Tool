"""main 入口:图标 URL 字典构造。"""
from lbs_ui_tool.__main__ import _build_icons_dict


def test_icons_dict_has_seven_keys():
    d = _build_icons_dict()
    assert set(d.keys()) == {"home", "connected", "disconnected",
                             "firmware", "monitor", "sensor", "python"}


def test_icons_dict_values_are_file_urls():
    d = _build_icons_dict()
    for k, v in d.items():
        assert v.startswith("file:///"), f"{k}: {v!r}"


def test_icons_dict_handles_chinese_filenames():
    """中文文件名(含中文逗号)在 URL 里应被 URL-encoded。"""
    d = _build_icons_dict()
    # 断开图标名字含中文逗号,URL 中不应保留裸中文逗号
    assert "," not in d["disconnected"], d["disconnected"]

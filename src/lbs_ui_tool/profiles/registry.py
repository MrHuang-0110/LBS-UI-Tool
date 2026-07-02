"""产品注册表。

按产品名构造 profile,集中管理。注册表映射产品名 -> profile 类,
``list_products`` 返回所有已注册产品名,``get_profile`` 按名取类并用
给定的 ``transport`` 实例化。
"""
from lbs_ui_tool.profiles.base import ProductProfile
from lbs_ui_tool.profiles.new_ai import NewAiProfile
from lbs_ui_tool.profiles.spark_ai import SparkAiProfile
from lbs_ui_tool.profiles.next_ai import NextAiProfile
from lbs_ui_tool.protocol.serial_transport import SerialTransport

_REGISTRY: dict[str, type[ProductProfile]] = {
    "NEW-AI": NewAiProfile,
    "SPARK-AI": SparkAiProfile,
    "NEXT-AI": NextAiProfile,
}


def list_products() -> list[str]:
    """返回所有已注册产品名。"""
    return list(_REGISTRY.keys())


def get_profile(name: str, transport: SerialTransport) -> ProductProfile:
    """按产品名构造 profile 实例。未知产品名抛 KeyError。"""
    cls = _REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"未知产品: {name}")
    return cls(transport)

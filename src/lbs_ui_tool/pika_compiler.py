# src/lbs_ui_tool/pika_compiler.py
"""调用 rust-msc-latest-win10.exe 编译 .py -> .o"""
import os
import subprocess
from pathlib import Path

DEFAULT_COMPILER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "rust-msc-latest-win10.exe",
)


class PikaCompiler:
    def __init__(self, compiler_path: str = DEFAULT_COMPILER):
        self.compiler_path = compiler_path

    def compile(self, src_path: str, out_path: str | None = None) -> str:
        if out_path is None:
            out_path = str(Path(src_path).with_suffix(".o"))
        result = subprocess.run(
            [self.compiler_path, "-c", src_path, "-o", out_path],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode(errors="replace") or "编译失败")
        return out_path

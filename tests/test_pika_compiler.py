# tests/test_pika_compiler.py
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from lbs_ui_tool.pika_compiler import PikaCompiler
import pytest


def test_resolve_compiler_path():
    c = PikaCompiler(compiler_path="e:/LBS-UI-Tool/rust-msc-latest-win10.exe")
    assert c.compiler_path.endswith("rust-msc-latest-win10.exe")


def test_compile_invokes_subprocess(tmp_path):
    c = PikaCompiler(compiler_path="rust-msc-latest-win10.exe")
    src = tmp_path / "main.py"
    src.write_text("print('hi')")
    with patch("lbs_ui_tool.pika_compiler.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        out = c.compile(str(src))
        assert run.called
        args = run.call_args[0][0]
        assert "-c" in args and "-o" in args


def test_compile_failure_raises(tmp_path):
    c = PikaCompiler(compiler_path="rust-msc-latest-win10.exe")
    src = tmp_path / "main.py"
    src.write_text("print('hi')")
    with patch("lbs_ui_tool.pika_compiler.subprocess.run") as run:
        run.return_value = MagicMock(returncode=1, stdout=b"", stderr=b"syntax error")
        with pytest.raises(RuntimeError, match="syntax error"):
            c.compile(str(src))

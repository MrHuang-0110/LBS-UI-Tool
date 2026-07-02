# tests/profiles/test_base.py
import pytest
from lbs_ui_tool.profiles.base import (
    ProductProfile, FirmwareFile, FirmwarePackage, MonitorState, NotSupportedError,
)

def test_firmware_package_defaults():
    pkg = FirmwarePackage(files=[FirmwareFile("app", "a.bin", True)])
    assert pkg.files[0].partition == "app"

def test_update_sensors_default_raises():
    class Dummy(ProductProfile):
        name = "x"
        supports_sensor_update = False
        def handshake(self): pass
        def firmware_template(self): return FirmwarePackage([])
        def download_firmware(self, package, progress_cb): pass
        def deploy_python(self, o_path, slot, progress_cb): pass
        def enable_monitor(self, on): pass
        def parse_monitor(self, raw): return MonitorState()
    with pytest.raises(NotSupportedError):
        Dummy().update_sensors({})

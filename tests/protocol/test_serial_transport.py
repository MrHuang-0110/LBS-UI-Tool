from lbs_ui_tool.protocol.serial_transport import SerialTransport, FakeSerial


def test_fake_serial_roundtrip():
    s = FakeSerial()
    s.write(b"hello")
    assert s.read(5) == b"hello"


def test_transport_write_goes_to_serial():
    s = FakeSerial()
    t = SerialTransport(serial=s)
    t.write(b"\x5A")
    assert s.tx == b"\x5A"


def test_transport_read_callback_invoked():
    s = FakeSerial()
    s.feed(b"\x01\x02\x03")
    received = []
    t = SerialTransport(serial=s, on_data=received.append)
    t.read_once()
    assert received == [b"\x01\x02\x03"]


def test_list_ports_returns_list():
    ports = SerialTransport.list_ports()
    assert isinstance(ports, list)

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


def test_read_once_returns_empty_when_no_waiting():
    """F3: in_waiting=0 时 read_once 立即返回 b"",不调 read(避免阻塞)。"""
    fake = FakeSerial()
    # 保证 _rx 为空
    assert fake.in_waiting() == 0
    called = []
    orig_read = fake.read

    def spy_read(n):
        called.append(n)
        return orig_read(n)

    fake.read = spy_read
    t = SerialTransport(fake)
    assert t.read_once() == b""
    assert called == []  # 没有调 read


def test_list_ports_returns_dicts_with_description():
    """F4: list_ports 每项含 device 和 description(可能相等,若驱动没提供描述)。"""
    ports = SerialTransport.list_ports()
    assert isinstance(ports, list)
    for p in ports:
        assert isinstance(p, dict)
        assert "device" in p
        assert "description" in p

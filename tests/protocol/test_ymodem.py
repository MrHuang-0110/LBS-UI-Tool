"""YmodemTransfer 单测。

FakeSerial 有回环:host write 的字节同时进 tx(供断言)与 _rx(供 read 回环)。
为避免 YMODEM 等待 ACK 时误读自己写出的数据块字节,实现里 _read_byte 只返回
设备响应字节('C'/ACK/NAK/CAN),跳过回环产生的数据块字节(SOH/STX/EOT/payload/CRC)。
测试按完整发送流程预置设备响应序列: C ACK C ACK ACK ACK。
"""
from lbs_ui_tool.protocol.ymodem import YmodemTransfer, crc16_xmodem, SOH
from lbs_ui_tool.protocol.serial_transport import FakeSerial


def test_crc16_known_value():
    # CRC-16-XMODEM(poly 0x1021, init 0) of "123456789" 的标准校验向量为 0x31C3,
    # 与 binascii.crc_hqx(data, 0) 及 CRC RevEng 目录一致。
    # (计划文档中误写为 0x31C1,差 1 bit,非标准值——会与真实 NEXT-AI 设备 CRC 不符。)
    assert crc16_xmodem(b"123456789") == 0x31C3


def test_send_small_file_uses_soh_128():
    s = FakeSerial()
    tx = YmodemTransfer(s, block_size=128)
    # 设备响应序列,对应完整发送流程:
    #   C       握手开始
    #   ACK     文件名块
    #   C       请求继续(进入数据阶段)
    #   ACK     数据块(HELLO,1 块)
    #   ACK     空结束块
    #   ACK     EOT
    s.feed(b"C\x06C\x06\x06\x06")
    seen = []
    ok = tx.send("hello.bin", b"HELLO",
                 progress_cb=lambda sent, total: seen.append((sent, total)))
    assert ok
    # 第一个写出字节是文件名块的 mark;block_size=128 应使用 SOH(0x01)而非 STX(0x02)
    assert s.tx[0] == SOH
    # 文件名块包含文件名,数据块包含 payload
    assert b"hello.bin" in s.tx
    assert b"HELLO" in s.tx
    # progress 回调按 (sent, total) 触发,5 字节单块 -> (5, 5)
    assert seen == [(5, 5)]

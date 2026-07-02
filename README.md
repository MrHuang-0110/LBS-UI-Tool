# LBS UI Tool

上位机工具:通过蓝牙虚拟串口对 **NEW-AI / SPARK-AI / NEXT-AI** 三款产品完成
固件下载、监控、传感器更新(仅 NEW-AI)、Python 代码编辑与下发。

基于 PySide6(QML) + pyserial,三层架构:协议层(产品无关)
→ 适配器层(产品 profile)→ 应用层(`BackendBridge` 暴露给 QML)。

## 开发

```bash
pip install -e ".[dev]"
pytest                       # 全量单测(无硬件)
python -m lbs_ui_tool        # 启动 GUI(需图形环境)
```

无头环境/CI 下仅运行单测;QML 用 `qmllint` 做静态验证:

```bash
python -c "import PySide6,os;print(os.path.join(os.path.dirname(PySide6.__file__),'qmllint.exe'))"
# 用上面得到的路径对 src/lbs_ui_tool/qml 下的 .qml 文件运行
```

## 使用流程

1. 启动后首页选择产品(三张卡片)→ 进入工作区。
2. 工作区左侧连接栏:选 COM 口 → 点"连接"(产品型号由首页选定,自动传入)。
3. 左侧功能栏切换:
   - **固件**:按产品固件包结构选择各分区文件 → "开始更新"(后台线程下发)。
   - **监控**:打开开关,显示电量/版本/状态 + 端口卡片。
   - **传感器**(仅 NEW-AI):8 端口(A-H)各选设备类型 → "更新"。
   - **Python**:打开项目目录 → 编辑 → 编译(rust-msc)→ 选槽位(0-19)→ 下发。

固件下发与 Python 下发在 worker 线程执行,不卡 UI;下发期间监控自动暂停以独占串口。

## 产品支持矩阵

| 功能 | NEW-AI | SPARK-AI | NEXT-AI |
|------|:------:|:--------:|:-------:|
| 固件下载 | 分区(app/boot/config/version/music) | app + version | 单 bin(YMODEM) |
| 监控 | JSON(NewAiState) | JSON(WillAiState) | JSON(state) |
| 传感器更新 | ✅ 0x32 帧 | ❌ | ❌ |
| Python 下发 | 自定义帧 | 自定义帧 | YMODEM |
| MCU | STM32H723 | STM32F103 | APM32E103 |

## NEW-AI 传感器设备 ID

传感器更新页为 8 个端口(A-H)各选一个设备,组帧为 `0x32` 帧的 8 字节数据,
未选端口填 `0xFF`(保持不变)。设备 ID(源自固件源码 `motor.h` 等):

| 设备 | ID | 设备 | ID |
|------|----|------|----|
| 大电机 big_motor | 0xA1 | 摄像头 camera | 0xA7 |
| 颜色 color | 0xA2 | 灰度 gray | 0xA9 |
| 超声波 ultrasonic | 0xA3 | 灰度V2 gray_v2 | 0xB0 |
| 触摸 touch | 0xA4 | NFC nfc | 0xB2 |
| 小电机 small_motor | 0xA6 | 保持不动 | 0xFF |

例如端口 A=大电机、H=小电机,则 0x32 帧数据为
`A1 FF FF FF FF FF FF A6`(crc = sum & 0xFF = 0x04)。

## 文档

- 设计文档:`docs/specs/2026-07-01-lbs-ui-tool-design.md`
- 实施计划:`docs/plans/2026-07-02-lbs-ui-tool-implementation.md`

## 项目结构

```
src/lbs_ui_tool/
  protocol/      frame_codec / serial_transport / ymodem / frame_file_transfer
  profiles/      base + new_ai / spark_ai / next_ai + registry
  backend.py     BackendBridge(QML 桥,worker 线程,监控轮询)
  pika_compiler.py  封装 rust-msc-latest-win10.exe
  qml/           main.qml + ui/(HomePage/WorkspacePage/各功能页/Theme)
tests/           protocol/ profiles/ test_backend.py test_integration.py
```

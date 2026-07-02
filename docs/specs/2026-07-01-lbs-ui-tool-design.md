# 上位机工具设计文档

> 产品下载、监控、传感器更新、Python 代码编辑工具
> 支持 NEW-AI / SPARK-AI / NEXT-AI 三款产品(蓝牙芯片均使用 ECB02)
> 日期:2026-07-01

---

## 1. 目标与范围

构建一个桌面上位机工具,通过蓝牙(ECB02 SPP 透传,PC 端表现为虚拟 COM 口)对三款产品完成:

1. **固件下载(OTA)**:把 APP `.bin` 烧进设备。
2. **监控**:实时显示设备上报的传感器/系统状态。
3. **传感器更新**(仅 NEW-AI):发指令告诉主机更新哪个端口的传感器。
4. **Python 代码编辑**:内置多文件 IDE,编辑 `.py` → 编译为 `.o` → 下发到设备 → 运行/停止。

UI 风格:App Store 风格——首页大卡片、毛玻璃、圆角、动画。

## 2. 协议事实(地基)

三款产品协议分层如下,设计以此为唯一依据。

### 2.1 控制面(三家共用)

所有控制指令走自定义 `_AGREEMENT` 帧:

```
0x5A | sID=0x97 | oID=0x98 | len(1B) | index(1B) | data[len] | crc(1B) | 0xA5
```

- `crc` = 前面所有字节累加和 & 0xFF
- 通信物理层:ECB02 SPP 透传,MCU 侧 UART 115200 8N1。PC 端为虚拟 COM 口。
- 公共命令码:
  - `0xBA` 启用监控上报 / `0xBE` 禁用监控上报
  - `0xB6` 进入 Python 模式 / `0xB9` 退出 Python 模式

### 2.2 数据面(因产品而异)

| 产品 | 固件 OTA | Python `.o` 下发 | 存储落点 | 现成上位机脚本 |
|---|---|---|---|---|
| NEW-AI | 自定义帧文件传输 | 自定义帧文件传输 | 外部 QSPI Flash FATFS `1:app/<slot>.o` | 无 |
| SPARK-AI | 自定义帧文件传输 | 自定义帧文件传输 | 外部 SPI Flash FATFS | 无 |
| NEXT-AI | YMODEM | YMODEM | FATFS | `tools/lbs_fw_update.py`、`tools/pika_deploy.py`(仅参考逻辑,不直接 import,因其路径硬编码) |

**自定义帧文件传输**(NEW-AI / SPARK-AI):
- 公共分块流程:开始(创建/打开)→ `0xAA` 写数据块(128B/块,每块等设备 `0xFD` ACK)→ `0xBB` 接收完成保存 / `0xBC` 接收完成并刷新 UI。
- **NEW-AI 用专门命令码区分固件包内的不同分区**(非文件名),源码 `piKaNewAI-Boot2/Core/Inc/main.h:66-71`:

  | 命令码 | 宏 | 目标分区 | 去向 |
  |---|---|---|---|
  | 0xDA | COPY_APP_FILE | app | 内部 Flash |
  | 0xDB | COPY_BOOT_FILE | boot | 内部 Flash(引导分区,Boot1/Boot2 双引导) |
  | 0xDC | COPY_CONFIG_FILE | config | 外部 QSPI Flash FATFS |
  | 0xDD | COPY_VERSION_FILE | version | 外部 QSPI Flash FATFS |
  | 0xEC | COPY_MUSIC_FILE | music | 外部 QSPI Flash FATFS |

- **SPARK-AI**:固件包仅 app + version,用命令码 + 文件名组合区分;app→内部 Flash 0x08010000,version→外部 SPI Flash FATFS。
- 注:NEW-AI 这套分区命令码是固件更新专用;Python `.o` 下发仍走 `0xDA`(创建文件)+ `0xAA`/`0xBB` 到外部 QSPI FATFS `1:app/<slot>.o`,与固件分区的 `0xDA` 含义不冲突(由当前是否处于 BOOT 升级态区分)。

**YMODEM**(NEXT-AI):
- 标准 YMODEM,CRC-16
- USB:STX 1024B 块;蓝牙:SOH 128B 块
- 流程:发 `C` → 文件头块 → 数据块 → EOT → ACK

### 2.3 监控数据

- 承载:`_AGREEMENT` 帧的 JSON 字符串(经 USB/BT 上报)。
- schema 各家不同:
  - NEW-AI:`deviceList`(8 类传感器)、`flash`、`version`、`bat`、IMU(yaw/pitch/roll)、`heap`、`NewAiState` 等。
  - SPARK-AI:`deviceList`(4 端口)、`flash`、`adc.bat`、`version`、`heap`、`WillAiState`。
  - NEXT-AI:字段更简(传感器/电池/内存/蓝牙/脚本状态/版本)。
- 启停:`0xBA` 启 / `0xBE` 停。

### 2.4 传感器更新(仅 NEW-AI)

指令帧:
```
5A 97 98 08 32 [A][B][C][D][E][F][G][H] crc A5
```
- `len=8`,`index=0x32`(传感器更新)。
- 8 个数据字节对应端口 A–H,每字节填**目标设备类型 ID**,`0xFF` = 保持不动。
  - 语义已在 `e:/LBS-NEW-AI/Drivers/DataFile/download/download.c` 核实:循环 0–7 端口,值为 `0xFF` 则跳过,否则作为该端口目标设备类型 ID。
- NEW-AI 支持的设备类型 ID(源码核实):

  | 宏名 | 值 | 含义 | 定义位置 |
  |---|---|---|---|
  | `DEV_ID_BIG_MOTOR` | 0xA1 | 大电机 | `Drivers/DataFile/motor/motor.h:12` |
  | `DEV_ID_SMALL_Motor` | 0xA6 | 小电机(即"中电机") | `Drivers/DataFile/motor/motor.h:13` |
  | `DEV_ID_COLOR` | 0xA2 | 颜色传感器 | `Drivers/DataFile/color/color.h:4` |
  | `DEV_ID_ULTRASION` | 0xA3 | 超声波传感器 | `Drivers/DataFile/ultrasion/ultrasion.h:5` |
  | `DEV_ID_TOUCH` | 0xA4 | 触摸传感器 | `Drivers/DataFile/touch/touch.h:5` |
  | `DEV_ID_CAMER` | 0xA7 | 摄像头传感器 | `Drivers/DataFile/camer/camer.h:5` |
  | `DEV_ID_GRAY` | 0xA9 | 灰度传感器 | `Drivers/DataFile/gray/gray.h:4` |
  | `DEV_ID_GRAY_V2` | 0xB0 | 第二代灰度传感器 | `Drivers/DataFile/grayv2/grayv2.h:5` |
  | `DEV_ID_NFC` | 0xB2 | NFC 传感器 | `Drivers/DataFile/nfc/nfc_car.h:5` |

- 校验:累加和 & 0xFF。样例 `...FF×8...BB A5` 经验证吻合。
- 注:SPARK-AI / NEXT-AI 虽也定义了设备类型 ID(电机 0xA1 / 颜色 0xA2 / 超声波 0xA3 / 触摸 0xA4),但**不支持传感器更新指令**,UI 整页灰显。

## 3. 技术选型

- **语言/框架**:Python 3 + PySide6(QML 做 UI)。
- **串口**:pyserial。
- **代码编辑器**:QML `TextEdit` + 自实现 Python 语法高亮(或嵌入轻量编辑器组件)。
- **图标**:内置矢量图标库(Material Icons / Lucide)+ 渐变配色。品牌素材(产品封面、logo)用占位图,留 `assets/` 接口,后续替换文件不改代码。
- **YMODEM**:参考 NEXT-AI 脚本逻辑从头实现为协议层独立组件,不直接 import 硬编码脚本。

## 4. 架构(产品适配器 + 共享协议层)

```
┌─────────────────────────────────────────────────┐
│  QML UI 层 (App Store 风格)                       │
│  首页卡片 / 工作区(功能栏+内容区) / 各功能页     │
│  仅通过 BackendBridge 调用,不碰串口              │
└───────────────────┬─────────────────────────────┘
                    │ Qt signals/slots
┌───────────────────▼─────────────────────────────┐
│  应用层  BackendBridge (单例,暴露给 QML)          │
│  管理产品选择/连接状态/任务编排/进度回调           │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│  适配器层  ProductProfile (抽象基类)              │
│   ├ NewAiProfile   ├ SparkAiProfile  ├ NextAiProfile│
│   各自实现:握手/固件/Python/监控解析/传感器更新    │
└───────────────────┬─────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│  协议层 (产品无关,可独立单测)                     │
│   FrameCodec        _AGREEMENT 编解码 + 累加和校验│
│   SerialTransport   pyserial 收发 + 线程化读取    │
│   YmodemTransfer    YMODEM-1K/128 CRC16 (NEXT用)  │
│   FrameFileTransfer 自定义帧文件传输(N/A + SPARK) │
└─────────────────────────────────────────────────┘
```

### 4.1 ProductProfile 抽象接口

```python
class ProductProfile(ABC):
    name: str
    device_hint: str            # 用于提示的设备名/标识
    supports_sensor_update: bool

    @abstractmethod
    def handshake(self) -> bool: ...
    @abstractmethod
    def download_firmware(self, package: FirmwarePackage, progress_cb) -> None: ...
    @abstractmethod
    def deploy_python(self, o_path: str, slot: int, progress_cb) -> None: ...
    @abstractmethod
    def enable_monitor(self, on: bool) -> None: ...
    @abstractmethod
    def parse_monitor(self, raw: bytes) -> MonitorState: ...
    def update_sensors(self, ports: dict[str, int]) -> None:
        raise NotSupportedError
```

- `update_sensors` 仅 `NewAiProfile` 实现;`NextAiProfile`/`SparkAiProfile` 用默认实现抛 `NotSupportedError`,UI 据此灰显。
- 进度统一通过 `progress_cb(percent, message)` 上报。

`FirmwarePackage` 描述固件包(因产品而异):

```python
@dataclass
class FirmwareFile:
    partition: str       # "app" / "boot" / "config" / "music" / "version" / ""(单 bin)
    path: str            # 本地文件路径
    required: bool       # 是否必选

@dataclass
class FirmwarePackage:
    files: list[FirmwareFile]
```

- 各 profile 暴露 `firmware_template()` 返回该产品的包模板(NEXT 单 bin、SPARK app+version、NEW app/boot/config/music/version),UI 据此渲染文件选择区。用户填好路径后构成 `FirmwarePackage` 传入 `download_firmware`,profile 内部按分区命令码/协议逐个下发。

### 4.2 并发模型

- 串口读取放独立 `QThread`,读循环按帧边界切分后丢给 profile 解析。
- 长任务(固件/Python/传感器)在工作者线程执行,通过 Qt signal 上报进度,UI 线程只渲染。
- `usbDownloadActive` 等价语义:下载进行时暂停监控解析,避免抢占串口。

### 4.3 统一进度契约

所有长任务通过同一信号:
```
progress(percent: 0..100, stage: str, detail: str)
task_finished(success: bool, message: str)
```
QML 用同一套进度浮层组件承接。

## 5. UI 设计

### 5.1 整体骨架:首页卡片 → 工作区

**首页**:三张大卡片(NEW-AI / SPARK-AI / NEXT-AI),每张含产品名、MCU 标识、连接状态点、封面图占位。点击进入工作区。

**工作区**:顶部返回 + 产品名;左侧功能栏(固件/监控/传感器/Python);右侧内容区随选中功能切换。传感器页对不支持的产品整体灰显并提示。

### 5.2 视觉风格(App Store)

- 圆角卡片(16–24px)、毛玻璃半透明背景、柔和投影。
- 渐变配色,每款产品一个主色(占位,可改)。
- SF Pro 风格字体(系统字体回退)。
- 转场动画(卡片点击放大进入、页面横向滑动)。
- 微交互(hover 抬升、按下缩放、状态点呼吸)。

### 5.3 各功能页

**固件下载页**:
- 固件包结构因产品而异,UI 按 profile 暴露的包清单渲染:
  - **NEXT-AI**:选单个 `.bin` → 整体 YMODEM 下发。
  - **SPARK-AI**:选 `app` + `version` 两个文件 → 按 profile 顺序下发。
  - **NEW-AI**:选 `app` / `boot` / `config` / `music` / `version` 五个文件(可只更新部分,未选的跳过)→ 按分区命令码(0xDA/0xDB/0xDC/0xDD/0xEC)逐个下发。
- 每个文件独立进度(块号/CRC/百分比),整体进度按文件加权。
- 进入升级(handshake/写 boot 标志/复位)由 profile 内部处理,UI 无感知。
- 协议分支(YMODEM vs 自定义帧、分区命令码)全部由 profile 内部决定,UI 只看统一的"文件清单 + 进度"接口。

**监控页**:
- 启用/停止开关。
- 端口传感器卡片网格 + 电量/版本/内存 + 实时折线图(数值随时间)。
- UI 只认 `MonitorState` 统一结构,不直接处理各家 JSON。

**传感器更新页**(仅 NEW-AI):
- 8 个端口槽 A–H,每个下拉选设备类型(大电机 0xA1 / 小电机 0xA6 / 颜色 0xA2 / 超声波 0xA3 / 触摸 0xA4 / 摄像头 0xA7 / 灰度 0xA9 / 灰度V2 0xB0 / NFC 0xB2),"保持不动"=0xFF。
- "更新"按钮 → 发 `0x32` 帧 → 等 ACK → 提示结果。

**Python IDE 页**:
- 左:文件树(项目目录,多文件)。
- 中:语法高亮编辑器。
- 右/下:控制台(编译输出 + 串口日志)。
- 工具栏:保存 / 编译(.py→.o,调 `rust-msc-latest-win10.exe`) / 选槽位(用户选) / 下发 / 运行(0xB6)/ 停止(0xB9)。
- 编译在临时目录进行,下发 `.o` 到用户选定槽位。

### 5.4 图片素材

- 功能图标/控件图标:内置矢量图标库。
- 品牌素材(产品封面、logo):`assets/` 占位图,文件名约定(如 `new_ai_cover.png`),后续替换文件不改代码。

## 6. 错误处理

- 串口打开失败/掉线:全局提示,自动停止进行中的任务,UI 回到未连接态。
- 帧校验失败:丢弃,统计错误计数,UI 角标显示。
- ACK 超时:重试 N 次(N 可配),仍失败则任务失败并提示。
- 编译失败:控制台展示 `rust-msc-latest-win10.exe` 的 stderr,不允许下发。
- 不支持的功能(如对 NEXT/SPARK 触发传感器更新):UI 灰显 + 提示,后端抛 `NotSupportedError` 兜底。

## 7. 测试策略

- **协议层单测(纯 Python,无硬件)**:
  - `FrameCodec`:编解码、累加和校验、边界(空数据、最大 256B、错帧头/帧尾)。
  - `FrameFileTransfer`:用 mock 串口模拟设备 ACK(`0xFD`)流程,验证分块与重试。
  - `YmodemTransfer`:用 mock 串口模拟 `C`/ACK/NAK,验证 STX/SOH 块构造与 CRC16。
  - 传感器帧:`0x32` 帧构造,含样例 `FF×8 → BB` 回归。
- **Profile 单测**:mock 串口,验证各家握手/固件/Python/监控解析分支。
- **UI 冒烟**:启动、切产品、切功能页、未连接态灰显。UI 与协议解耦,可离线测。

## 8. 范围外(YAGNI)

- 不做 BLE 自动扫描连接(用户已选手动选口+型号)。
- 不做 OTA 断点续传(YMODEM 标准支持则保留,自定义帧不额外实现)。
- 不做云端/账号/多设备并发。
- 不做固件签名校验(协议未定义)。

## 9. 待实现时核对项(不阻塞设计)

- 各家监控 JSON 字段的精确键名与类型(实现 `parse_monitor` 时核对 `monitor.c`/`json-maker.c`)。
- NEW-AI/SPARK 进入 BOOT 升级的具体触发(写 `updata.txt`/boot magic)——实现 `download_firmware` 时核对 BOOT 源码。
- (传感器设备类型 ID 已在 §2.4 落实,不再为待核对项。)

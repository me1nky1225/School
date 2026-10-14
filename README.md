# 基于 ESP32 的环境检测与智能报警系统

《物联网应用系统》课程设计。系统以 ESP32 为核心，采集温湿度、超声波距离、光照等环境数据，通过 MQTT 接入 OneNET 云平台，并在 OLED 屏上以菜单形式交互；用户可通过微信小程序远程查看数据并控制灯光、蜂鸣器。

```text
DHT11 / HC-SR04 / 光敏 ──► ESP32 (MicroPython) ──MQTT──► OneNET 云平台
                                │                           │
                        SSD1306 OLED + 按键            REST API（物模型）
                        蜂鸣器 + 流水灯 + WS2812B           │
                                                    微信小程序上位机
```

## 项目结构

```text
课设源码/
├── ESP32源码/                    # MicroPython 设备端代码
│   ├── boot.py                   # 上电自动运行：连接 WiFi
│   ├── main.py                   # 主程序：采集/报警/OLED菜单/MQTT
│   ├── simple.py                 # MQTT 客户端库（第三方）
│   ├── ssd1306.py                # OLED 驱动（第三方）
│   ├── hcsr04.py                 # 超声波驱动（第三方）
│   ├── Dht11.py                  # 单模块测试程序（不参与最终运行）
│   └── BuzzerBeep.py             # 单模块测试程序（不参与最终运行）
└── 微信小程序源码/
    └── weapp/                    # 微信开发者工具项目
        ├── config/onenet.js      # OneNET 配置（需填写自己的凭证）
        ├── utils/onenet.js       # OneNET REST API 封装
        ├── pages/home/           # 监控页：环境数据 + 执行器状态
        ├── pages/control/        # 控制页：LED/幻彩灯/蜂鸣器远程控制
        └── pages/device/         # 设备页：连接诊断、刷新间隔设置
```

## 硬件清单

| 模块 | 型号/规格 | 接口 |
|---|---|---|
| 主控 | ESP32-WROOM-32 开发板 | — |
| 温湿度传感器 | DHT11 | 单总线 |
| 超声波测距 | HC-SR04 | Trig/Echo |
| 光照传感器 | 光敏电阻模块（AO 模拟输出） | ADC |
| 显示屏 | 0.96 寸 SSD1306 OLED（128×64） | I2C |
| 报警 | 无源蜂鸣器 | PWM |
| 幻彩灯 | WS2812B 灯珠 × 9 | 单总线 |
| 灯组 | 8 路 LED 流水灯 | GPIO |
| 按键 | 独立按键 × 4（K1~K4） | GPIO |

## 引脚定义

| 外设 | 引脚 | GPIO | 备注 |
|---|---|---|---|
| DHT11 数据脚 | DATA | 21 | 单总线，需上拉 |
| HC-SR04 | TRIG / ECHO | 33 / 27 | |
| 光敏 AO | AO | 34 | ADC1 输入，量程 0~3.3V |
| 无源蜂鸣器 | I/O | 0 | PWM 驱动，报警 2000Hz |
| WS2812B | DIN | 15 | 共 9 颗 |
| OLED | SCL / SDA | 14 / 13 | I2C，100kHz |
| 8 路流水灯 | D1~D8 | 16, 17, 18, 19, 23, 5, 2, 22 | 其中 22 与板载 LED 共用 |
| 按键 K1~K4 | I/O | 32, 25, 26, 4 | 内部上拉，按下为低电平 |
| 板载 LED | — | 22 | 低电平点亮，boot.py 用作 WiFi 连接指示 |

## 报警逻辑与默认阈值

报警优先级：**距离/手动 > 湿度 > 光照 > 云端手动**，高优先级报警会接管对应灯光。

| 触发条件 | 灯光效果 | 蜂鸣器 | 解除条件 |
|---|---|---|---|
| 距离 < 报警阈值（默认 10cm） | 幻彩灯红灯闪 + 8 路LED同闪 | 2000Hz 间歇音 | 距离恢复 |
| 湿度 ≥ 75%RH | 幻彩灯蓝灯闪 | 2000Hz 间歇音 | 湿度 < 70%RH |
| 光照过强（ADC < 1800） | 幻彩灯绿灯闪 | 2000Hz 间歇音 | ADC > 2100 |
| 云端手动开启 | 不接管灯光 | 2000Hz 持续音 | 云端关闭 |
| OLED 手动报警 | 同距离报警 | 同距离报警 | K3 再次切换 |

代码内可调参数（`main.py`）：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `alarm_threshold` | 10 | 距离报警阈值(cm)，可在 OLED 报警页用 K1/K2 调节 2~100 |
| `HUM_ON_THRESHOLD` / `HUM_OFF_THRESHOLD` | 75 / 70 | 湿度报警触发/解除阈值，回差防抖 |
| `LIGHT_ON_THRESHOLD` / `LIGHT_OFF_THRESHOLD` | 1800 / 2100 | 光照触发/解除阈值（ADC 原始值，越小越亮） |
| `DHT_INTERVAL_MS` | 2000 | DHT11 采样间隔（硬件要求 ≥1s） |

## 配置流程

### 1. 烧录 MicroPython 固件

下载 ESP32 通用版 MicroPython 固件，使用 Thonny IDE（解释器选择 MicroPython ESP32）或 esptool 烧录：

```bash
esptool.py --chip esp32 --port COMx erase_flash
esptool.py --chip esp32 --port COMx --baud 460800 write_flash -z 0x1000 esp32-xxxx.bin
```

随后将以下文件上传到设备根目录：`boot.py`、`main.py`、`simple.py`、`ssd1306.py`、`hcsr04.py`（`dht`、`neopixel` 为固件内置模块）。

### 2. OneNET 平台

1. 注册并登录 [OneNET](https://open.iot.10086.cn/)，进入开发者中心，**创建产品**（接入协议选择 MQTT），再**创建设备**，记下「产品 ID」和「设备名称」。
2. 在产品的**物模型**中添加下表 8 个属性（功能点）。
3. 生成设备 token：控制台右上角「访问权限」获取 AccessKey，用官方 Token 工具填写：
   - `res` = `products/{产品ID}/devices/{设备名称}`
   - `et` = 过期时间戳（秒）
   - `method` = 与工具保持一致（md5 或 sha1）

### 3. ESP32 端配置

| 文件 | 配置项 | 说明 |
|---|---|---|
| `boot.py` | `ssid_c` / `password` | WiFi 热点名与密码 |
| `main.py` | `NAME` / `CLIENT_ID` / `PSWD` | 产品 ID / 设备名称 / 生成的 token |

`main.py` 中的 4 条 MQTT 主题同样使用占位符，部署前请**全局替换**以下两个占位符（含主题行共 6 处）：

- `your_product_id` → 你的产品 ID
- `your_device_name` → 你的设备名称

### 4. 微信小程序配置

1. 用[微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)导入 `微信小程序源码/weapp` 目录；appid 可使用测试号（默认 `touristappid`）。
2. 编辑 `config/onenet.js`，填入自己的 `productId`、`deviceName`、`token`。
3. 开发阶段在「详情 → 本地设置」勾选「不校验合法域名」；正式发布需在小程序后台将 `https://iot-api.heclouds.com` 配置为 request 合法域名。

## 物模型属性

与 ESP32 端 `main.py` 上报、小程序端 `utils/onenet.js` 调用保持一致：

| 标识符 | 类型 | 方向 | 说明 |
|---|---|---|---|
| `temp_value` | float | 上报 | 温度 (℃) |
| `humidity_value` | int | 上报 | 湿度 (%RH) |
| `distance_value` | float | 上报 | 距离 (cm) |
| `light_value` | int | 上报 | 光敏 ADC 原始值 0~4095，越小越亮 |
| `led_switch` | bool | 下发 | 旧版流水灯开关（映射为模式 1/0） |
| `led8_mode` | int 0/1/2 | 下发 | 8 路 LED：关 / 流水 / 闪烁 |
| `rgb_mode` | int 0/1/2 | 下发 | WS2812B：关 / 呼吸 / 跑马 |
| `buzzer_switch` | bool | 下发 | 手动鸣响 |

## 使用说明

### OLED 菜单（4 按键）

按键功能：**K1** 上移/增大阈值，**K2** 下移/减小阈值，**K3** 确定/切换手动报警，**K4** 返回。

```text
主菜单 Menu
├── Status       环境状态页（温湿度 / 距离 / 报警状态）
├── LED Control
│   ├── Water Lamp   8路流水灯：Off / Flow / Blink
│   └── RGB LED      幻彩灯：Off / Breath / Chase
├── Network      网络信息页（SSID / IP / 网关 / 子网掩码）
└── Alarm        报警设置页（距离阈值调节 / 手动报警开关）
```

### 微信小程序

- **监控页**：温湿度、距离、光照四张数据卡片 + 执行器状态，支持下拉刷新。
- **控制页**：8 路 LED 模式（关闭/流水/闪烁）、WS2812B 模式（关闭/呼吸/跑马）、蜂鸣器开关与「全部关闭」。
- **设备页**：向 OneNET 发起属性查询验证连通性，调整自动刷新间隔。

## 常见问题

- **MQTT 连接失败 / 收到云端口令错误**：检查 token 是否填写正确、是否已过期（`et` 字段），过期后用工具重新生成。
- **DHT11 偶发读取失败**：正常现象，程序已做 3 次重试并保留上次有效读数；两次采样间隔请勿小于 1s。
- **光照读数异常锁死在“光照强”**：蜂鸣器工作时的电源干扰会影响 ADC，程序已在每次采样前关闭蜂鸣器并做 16 次均值滤波，若仍异常请检查模块供电。
- **小程序查不到数据**：确认设备已连接 OneNET 且在持续上报，再通过设备页发起一次查询验证 token 与网络。

## 隐私说明

本仓库代码中所有敏感凭证均已替换为占位符，使用前按下表替换为自己的信息：

| 文件 | 占位符 | 含义 |
|---|---|---|
| `ESP32源码/boot.py` | `your_wifi_ssid` / `your_wifi_password` | WiFi 热点 |
| `ESP32源码/main.py` | `your_product_id` / `your_device_name` / `your_onenet_token` | OneNET 平台 |
| `微信小程序源码/weapp/config/onenet.js` | `your_product_id` / `your_device_name` / `your_onenet_token` | OneNET 平台 |
| `微信小程序源码/weapp/project.config.json` | `touristappid` | 可替换为自己的小程序 appid |

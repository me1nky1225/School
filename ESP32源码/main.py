# -*- coding: utf-8 -*-
# ==============================================================================
# 项目名称：基于 ESP32 的环境检测与智能报警系统
# 课程名称：《物联网应用系统》课程设计
# 开发时间：2026-09
# 开发环境：ESP32-WROOM-32 + MicroPython + Thonny IDE
# ------------------------------------------------------------------------------
# 文件说明：系统主程序，在 boot.py 完成 WiFi 连接后运行。
# 整合功能：DHT11 温湿度采集 + HC-SR04 超声波测距 + 光敏 ADC 光照检测 +
#           SSD1306 OLED 显示与四按键菜单 + MQTT 上传 OneNET 云平台 +
#           蜂鸣器声光报警 + 8 路流水灯 + WS2812B 幻彩灯 + 小程序远程控制。
# 程序结构：引脚定义 → 外设初始化 → 工具函数 → 报警与灯光控制 → 传感器采集 →
#           MQTT 收发 → OLED 菜单状态机 → 主循环（非阻塞分时调度）。
# ==============================================================================
from simple import MQTTClient
import json, time, gc
import network
from machine import Pin, I2C, PWM, ADC
import ssd1306               #需要在设备同目录下，创建ssd1306.py程序
import dht                   #dht库，包含DHT11温湿度传感器的常用驱动函数
from hcsr04 import HCSR04
import neopixel              #WS2812B幻彩灯驱动

gc.collect()   #程序运行前，调用内存垃圾回收

# -------------------- 引脚定义 --------------------
DHT_PIN = 21          # DHT11温湿度传感器数据脚
TRIG_PIN = 33         # HC-SR04触发脚
ECHO_PIN = 27         # HC-SR04回波脚
BUZZER_PIN = 0        # 无源蜂鸣器
WS2812_PIN = 15       # WS2812B幻彩灯数据脚
WS2812_NUM = 9        # WS2812B灯珠数量
OLED_SCL = 14         # OLED时钟脚
OLED_SDA = 13         # OLED数据脚
LED8_PINS = [16, 17, 18, 19, 23, 5, 2, 22]   # 8个流水灯
KEY_PINS = [32, 25, 26, 4]                    # K1上 K2下 K3确定 K4返回
LIGHT_PIN = 34        # 光敏传感器模拟输出脚(ADC)

# 光敏控制参数
LIGHT_ON_THRESHOLD = 1800   # 光照强(ADC低于此值)触发蜂鸣器
LIGHT_OFF_THRESHOLD = 2100  # 光照弱(ADC高于此值)停止，回差避免临界抖动

# 湿度报警参数
HUM_ON_THRESHOLD = 75       # 湿度达到此值触发蜂鸣器报警
HUM_OFF_THRESHOLD = 70      # 湿度低于此值解除报警，回差避免临界抖动

# -------------------- 外设初始化 --------------------
# 按引脚定义一次性创建各外设对象，避免在主循环中反复创建对象造成内存碎片
d = dht.DHT11(Pin(DHT_PIN))                                 # 温湿度传感器（单总线）
sonar = HCSR04(trigger_pin=TRIG_PIN, echo_pin=ECHO_PIN)     # 超声波测距
buzzer = PWM(Pin(BUZZER_PIN), freq=2000, duty=0)            # 无源蜂鸣器，duty=0 表示初始静音
np = neopixel.NeoPixel(Pin(WS2812_PIN), WS2812_NUM)         # WS2812B 幻彩灯，共9颗

led8 = [Pin(p, Pin.OUT) for p in LED8_PINS]                 # 8路流水灯，全部配置为输出
keys = [Pin(p, Pin.IN, Pin.PULL_UP) for p in KEY_PINS]      # 4个按键，内部上拉，按下为低电平
light_adc = ADC(Pin(LIGHT_PIN))                 # 光敏传感器ADC
light_adc.atten(ADC.ATTN_11DB)                  # 量程0~3.3V

# OLED 使用 I2C 接口，100kHz 足够且更稳定
i2c = I2C(scl=Pin(OLED_SCL), sda=Pin(OLED_SDA), freq=100000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# -------------------- 全局变量 --------------------
temp_ = ''           # 温度
hum_ = ''            # 湿度
distance_ = None     # 距离(cm)
alarm_threshold = 10 # 报警阈值(cm)
alarm_active = False # 距离过近报警状态
manual_alarm = False # 手动报警开关
buzzer_cmd = False   # 云端指令控制的蜂鸣器状态
light_value = 0      # 光敏ADC原始值(0~4095)
light_trigger = False  # 光照触发蜂鸣器状态
hum_alarm = False    # 湿度过高报警状态

# -------------------- 菜单状态 --------------------
# OLED 界面采用有限状态机管理，state 表示当前所在界面，cursor 表示光标所在项
ST_MAIN = 0        # 主菜单
ST_STATUS = 1      # 环境状态显示页
ST_LED = 2         # 灯光控制二级菜单
ST_LED8 = 3        # 8路流水灯模式选择页
ST_RGB = 4         # 幻彩灯模式选择页
ST_NET = 5         # 网络信息页
ST_BUZZER = 6      # 报警设置页

state = ST_MAIN
cursor = 0

# LED模式：0关 1流水 2闪烁
led8_mode = 0
# 幻彩模式：0关 1呼吸灯 2跑马灯
rgb_mode = 0

# -------------------- 工具函数 --------------------
def to_bool(v):
    """健壮解析云端下发的布尔值：兼容 bool / int / str 三种类型
    若物模型类型不是 bool，OneNET 可能下发 'false'、'0' 这类字符串，
    直接 bool('false') 会得到 True，导致开关关不掉。"""
    if isinstance(v, str):
        return v.strip().lower() in ('1', 'true', 'on', 'yes')
    return bool(v)

def to_mode(v):
    """把云端下发的模式值限制在 0~2"""
    try:
        m = int(v)
    except (ValueError, TypeError):
        return 0
    return max(0, min(2, m))

# -------------------- 蜂鸣器 --------------------
def buzzer_on(freq=2000):
    buzzer.freq(freq)
    buzzer.duty(512)

def buzzer_off():
    buzzer.duty(0)

# -------------------- WS2812B --------------------
def ws_set(i, r, g, b):
    # 这颗幻彩灯为RGB数据顺序，直接存(r, g, b)
    np[i] = (r, g, b)

def ws_fill(r, g, b):
    for i in range(WS2812_NUM):
        ws_set(i, r, g, b)

def ws_clear():
    ws_fill(0, 0, 0)

def led8_apply(now):
    """按当前模式驱动8路流水灯"""
    if led8_mode == 0:                       # 关闭
        for l in led8:
            l.value(0)
    elif led8_mode == 1:                     # 流水灯
        pos = (now // 120) % 8
        for i, l in enumerate(led8):
            l.value(1 if i == pos else 0)
    elif led8_mode == 2:                     # 闪烁
        on = (now // 300) % 2
        for l in led8:
            l.value(on)

# -------------------- 按键扫描（下降沿+去抖） --------------------
key_prev = [1, 1, 1, 1]      # 上一次的电平状态，用于判断下降沿（按下瞬间）
key_last = [0, 0, 0, 0]      # 上一次被确认按下的时刻，用于软件去抖

def read_keys():
    """扫描4个按键，返回本次被按下的按键序号列表（可能为空）。

    采用"下降沿检测 + 150ms 时间窗去抖"：
    只有电平由高变低（1→0）且距上次确认超过150ms才计为一次有效按下，
    这样既保证单击灵敏，又能避免机械抖动导致的连击。
    """
    global key_prev
    pressed = []
    now = time.ticks_ms()
    for i in range(4):
        v = keys[i].value()
        if key_prev[i] == 1 and v == 0:           # 检测到按下（下降沿）
            if time.ticks_diff(now, key_last[i]) > 150:
                key_last[i] = now
                pressed.append(i)
        key_prev[i] = v
    return pressed

# -------------------- LED动画更新 --------------------
def update_leds():
    """按报警优先级刷新所有灯光，每 30ms 由主循环调用一次。

    报警优先级（高→低）：距离/手动 > 湿度 > 光照 > 正常灯光模式。
    一旦命中高优先级分支即 return，避免多类报警同时触发时灯光互相覆盖；
    其中距离报警会同时接管 8 路流水灯，湿度/光照报警只接管幻彩灯，
    8 路流水灯仍按用户菜单所选的模式运行。
    """
    global led8_mode, rgb_mode
    now = time.ticks_ms()

    # 距离/手动报警优先：幻彩红灯闪烁 + 8路LED一同闪烁
    if alarm_active or manual_alarm:
        on = (now // 250) % 2
        if on:
            ws_fill(255, 0, 0)
            for l in led8:
                l.value(1)
        else:
            ws_clear()
            for l in led8:
                l.value(0)
        np.write()
        return

    # 湿度过高：幻彩蓝灯闪烁，8路流水灯保持原有模式
    if hum_alarm:
        on = (now // 250) % 2
        if on:
            ws_fill(0, 0, 255)
        else:
            ws_clear()
        np.write()
        led8_apply(now)
        return

    # 光照触发：幻彩绿灯闪烁，8路流水灯保持原有模式
    if light_trigger:
        on = (now // 250) % 2
        if on:
            ws_fill(0, 255, 0)
        else:
            ws_clear()
        np.write()
        led8_apply(now)
        return

    # 8路流水灯
    led8_apply(now)

    # WS2812B幻彩灯
    if rgb_mode == 0:                        # 关闭
        ws_clear()
    elif rgb_mode == 1:                      # 呼吸灯（紫色）
        b = abs(((now // 8) % 200) - 100) / 100.0
        v = int(b * 255)
        ws_fill(v, 0, v)
    elif rgb_mode == 2:                      # 跑马灯
        pos = (now // 120) % WS2812_NUM
        ws_clear()
        ws_set(pos, 0, 255, 255)
    np.write()

def update_buzzer():
    """刷新蜂鸣器状态，与 update_leds() 同周期调用（每 30ms）。

    优先级与灯光保持一致：距离/手动 > 湿度 > 光照 > 云端手动开关。
    前三类报警统一输出 2000Hz 间歇音（响400ms、停400ms），
    云端手动开启时输出 2000Hz 持续音，便于用声音区分"报警"和"人为控制"。
    """
    global buzzer_cmd
    if alarm_active or manual_alarm:
        # 距离/手动报警：2000Hz 间歇音
        if (time.ticks_ms() // 400) % 2 == 0:
            buzzer_on(2000)
        else:
            buzzer_off()
    elif hum_alarm:
        # 湿度过高：与距离报警同频率 2000Hz 间歇音
        if (time.ticks_ms() // 400) % 2 == 0:
            buzzer_on(2000)
        else:
            buzzer_off()
    elif light_trigger:
        # 光照触发：与距离报警同频率 2000Hz 间歇音
        if (time.ticks_ms() // 400) % 2 == 0:
            buzzer_on(2000)
        else:
            buzzer_off()
    elif buzzer_cmd:
        # 云端手动开关：与其他报警统一 2000Hz，持续鸣响
        buzzer_on(2000)
    else:
        buzzer_off()

# -------------------- 传感器采集 --------------------
DHT_INTERVAL_MS = 2000     # DHT11两次采样最小间隔（硬件要求>=1s，取2s更稳）
last_dht_read = 0

def get_dht11():
    """读取 DHT11 温湿度并更新全局 temp_ / hum_。

    DHT11 硬件要求两次采样间隔不小于 1s，这里取 2s 更稳妥；
    若距上次采样不足最小间隔则直接返回，避免读取失败。
    读取失败时最多重试 3 次，全部失败则保留上一次的有效读数，
    防止因偶发超时把温度/湿度置空导致后续 float('') 崩溃。
    """
    global temp_, hum_, last_dht_read
    now = time.ticks_ms()
    # 若距上次采样不足最小间隔，直接返回上次数据
    if time.ticks_diff(now, last_dht_read) < DHT_INTERVAL_MS:
        return
    last_dht_read = now
    # 重试多次，提高稳定性
    for _ in range(3):
        try:
            d.measure()
            temp_ = str(d.temperature())
            hum_ = str(d.humidity())
            print('Temp:' + temp_ + ' C')
            print('Hum:' + hum_ + ' %')
            return
        except OSError:
            time.sleep_ms(50)
    # 三次都失败：保留上次读数，不崩溃
    print('DHT11 read timeout, keep last value')

def get_distance():
    """读取一次超声波距离，单位为厘米。

    驱动返回的是毫米值，这里除以10换算为厘米；
    超出量程（>4m）或无回波时驱动会抛出 OSError，
    此时把距离置为 None，由上报逻辑统一按 0.0 处理。
    """
    global distance_
    try:
        mm = sonar.distance_mm()
        distance_ = mm / 10.0      # 转成厘米
    except OSError:
        distance_ = None           # 超出量程或无回波
    print('Dist:', distance_, 'cm')
    return distance_

def update_light_auto():
    """光敏检测：光照强触发蜂鸣器"""
    global light_value, light_trigger
    # 采样前先关蜂鸣器，避免其电流/EMI干扰ADC导致读数锁死在"光照强"
    buzzer_off()
    time.sleep_ms(20)
    # 多次采样取平均，降低电源纹波干扰
    N = 16
    total = 0
    for _ in range(N):
        total += light_adc.read()
        time.sleep_ms(2)
    light_value = total // N
    # 迟滞控制：光照强(值小)触发，光照弱(值大)停止，避免临界抖动锁死
    if light_trigger:
        if light_value > LIGHT_OFF_THRESHOLD:
            light_trigger = False
    else:
        if light_value < LIGHT_ON_THRESHOLD:
            light_trigger = True
    print('Light:', light_value, 'trigger:', 'Y' if light_trigger else 'N')
    return light_trigger

# -------------------- 配置服务器信息（OneNET） --------------------
SERVER = 'mqtts.heclouds.com'
PORT = 1883
NAME = 'your_product_id'
CLIENT_ID = "your_device_name"
# 密码是工具生成的token
PSWD = 'your_onenet_token'   # 在OneNET官方Token工具中生成后粘贴到这里

#订阅和发布主题
publish_Topic = '$sys/your_product_id/your_device_name/thing/property/post'         # 用于ESP32发布信息到云端
post_Topic = '$sys/your_product_id/your_device_name/thing/property/post/reply'      # 用于ESP32订阅云端反馈信息
subscribe_Topic = '$sys/your_product_id/your_device_name/thing/property/set'        # 用于ESP32订阅云端配置指令
respose_Topic = '$sys/your_product_id/your_device_name/thing/property/set_reply'    # 用于ESP32发布指令执行反馈信息

# -------------------- MQTT 回调函数 --------------------
def MQTT_callback(topic, msg):
    """MQTT 消息回调，由 client.check_msg() 收到订阅消息时触发。

    本设备共订阅两个主题：
      1) .../thing/property/post/reply —— 数据上报后的云端回执，
         msg 为 success 时正常忽略，否则打印错误便于排查；
      2) .../thing/property/set       —— 云端下发的属性设置指令，
         由小程序控制页发起，需解析 params 执行动作，
         并向 set_reply 主题回执执行结果（OneNET 要求必须回执）。
    """
    global buzzer_cmd, led8_mode, rgb_mode
    #post/reply主题上报数据，如果是反馈信息则无动作
    if (str(topic) == "b'$sys/your_product_id/your_device_name/thing/property/post/reply'"):
        json_str = msg.decode('utf-8')
        dic_msg = json.loads(json_str)
        if(dic_msg["msg"] == 'success'):
            pass
        else:
            print("topic:{}".format(topic))
            print("msg:{}".format(msg))
    #否则为set主题下发的属性设置指令
    else:
        print("topic:{}".format(topic))
        print("msg:{}".format(msg))
        json_str = msg.decode('utf-8')
        dic_msg = json.loads(json_str)
        id = dic_msg['id']
        #字典类型
        res_msg_dic = {"id": id, "code": 200, "msg": "Received successly!"}
        #json类型
        res_msg_json = json.dumps(res_msg_dic)
        client.publish(topic=respose_Topic, msg=res_msg_json, retain=False, qos=0)
        params = dic_msg.get("params", {})
        # 8路LED：兼容旧的 led_switch 开关，以及新的 led8_mode 模式值(0关/1流水/2闪烁)
        if "led_switch" in params:
            led8_mode = 1 if to_bool(params["led_switch"]) else 0
        if "led8_mode" in params:
            led8_mode = to_mode(params["led8_mode"])
        # WS2812B幻彩灯：rgb_mode 模式值(0关/1呼吸/2跑马)
        if "rgb_mode" in params:
            rgb_mode = to_mode(params["rgb_mode"])
        # 蜂鸣器云端控制
        if "buzzer_switch" in params:
            buzzer_cmd = to_bool(params["buzzer_switch"])

# -------------------- 传感器采集 + MQTT发布 --------------------
def read_sensors_and_publish():
    """采集一轮数据并上报云端，每 1s 由主循环调用一次。

    执行顺序：读温湿度 → 读距离 → 更新距离报警 → 更新湿度报警（迟滞）→
    按 OneNET 物模型格式打包 JSON → 发布到属性上报主题。
    """
    global alarm_active, hum_alarm
    get_dht11()
    dist = get_distance()

    # 距离低于阈值即认为有障碍物过近，报警无迟滞（距离跳变明显，不易抖动）
    alarm_active = (dist is not None and dist < alarm_threshold)

    # 若温湿度尚无有效读数，跳过本次上报，避免 float('') 崩溃
    if temp_ == '' or hum_ == '':
        return
    t = float(temp_)
    h = int(hum_)

    # 湿度过高判断（迟滞控制，避免临界抖动）
    if hum_alarm:
        if h < HUM_OFF_THRESHOLD:
            hum_alarm = False
    else:
        if h >= HUM_ON_THRESHOLD:
            hum_alarm = True

    # MQTT信息，json格式
    mymessage = {
        "id": "123", "version": "1.0",
        "params": {
            "temp_value": {"value": t},                                  # 温度
            "humidity_value": {"value": h},                              # 湿度
            "distance_value": {"value": dist if dist is not None else 0.0},  # 距离
            "light_value": {"value": light_value},                           # 光照(ADC原始值，越小越亮)
            "led_switch": {"value": bool(led8_mode != 0)},               # 流水灯状态
            "led8_mode": {"value": led8_mode},                           # 流水灯模式(0关/1流水/2闪烁)
            "rgb_mode": {"value": rgb_mode},                             # 幻彩灯模式(0关/1呼吸/2跑马)
            "buzzer_switch": {"value": bool(alarm_active or manual_alarm or hum_alarm or light_trigger or buzzer_cmd)},# 蜂鸣器实际响铃状态
        }
    }
    msg_json = json.dumps(mymessage)
    client.publish(topic=publish_Topic, msg=msg_json)

# -------------------- OLED菜单绘制 --------------------
def draw_menu(title, items, cursor):
    """绘制通用列表菜单：标题在首行，光标所在项前加 '>' 标识。
    items 超过4项时行距自动收窄，保证 64 像素高度内可完整显示。
    """
    oled.fill(0)                          # 先清屏，避免新旧内容重叠
    oled.text(title, 0, 0)
    sp = 12 if len(items) <= 4 else 10    # 根据条目数自适应行距
    for i, it in enumerate(items):
        prefix = '>' if i == cursor else ' '
        oled.text(prefix + it, 0, 14 + i * sp)
    oled.show()                           # 写入显存后需 show() 才真正显示

def draw_status():
    oled.fill(0)
    oled.text('Temp: ' + temp_ + ' C', 0, 0)
    oled.text('Hum: ' + hum_ + ' %', 0, 16)
    if distance_ is None:
        oled.text('Dist: --- cm', 0, 32)
    else:
        oled.text('Dist: %.1f cm' % distance_, 0, 32)
    oled.text('Alarm: ' + ('ON' if (alarm_active or manual_alarm or hum_alarm or light_trigger) else 'OFF'), 0, 48)
    oled.show()

def draw_net():
    w = network.WLAN(network.STA_IF)
    ip, mask, gw, dns = w.ifconfig()
    ssid = w.config('essid')
    if isinstance(ssid, bytes):
        ssid = ssid.decode('utf-8')
    oled.fill(0)
    oled.text('SSID:' + ssid[:12], 0, 0)
    oled.text('IP:' + ip, 0, 16)
    oled.text('GW:' + gw, 0, 32)
    oled.text('MASK:' + mask, 0, 48)
    oled.show()

def draw_buzzer():
    oled.fill(0)
    oled.text('Alarm Threshold', 0, 0)
    oled.text(' < %dcm  %d%%RH' % (alarm_threshold, HUM_ON_THRESHOLD), 0, 14)
    oled.text('Manual: ' + ('ON' if manual_alarm else 'OFF'), 0, 28)
    oled.text('K1:+ K2:- K3:Manual', 0, 42)
    oled.text('K4:Back', 0, 52)
    oled.show()

def draw_current():
    global state, cursor
    if state == ST_MAIN:
        draw_menu('Menu', ['Status', 'LED Control', 'Network', 'Alarm'], cursor)
    elif state == ST_STATUS:
        draw_status()
    elif state == ST_LED:
        draw_menu('LED Control', ['Water Lamp', 'RGB LED'], cursor)
    elif state == ST_LED8:
        draw_menu('Water Lamp', ['Off', 'Flow', 'Blink'], cursor)
    elif state == ST_RGB:
        draw_menu('RGB LED', ['Off', 'Breath', 'Chase'], cursor)
    elif state == ST_NET:
        draw_net()
    elif state == ST_BUZZER:
        draw_buzzer()

# -------------------- 菜单按键处理 --------------------
def handle_keys(kp):
    """根据当前界面状态处理按键，实现菜单状态机的跳转。

    kp 为 read_keys() 返回的按键序号列表，约定：
        K1(索引0) = 上移 / 增大阈值    K2(索引1) = 下移 / 减小阈值
        K3(索引2) = 确定 / 应用 / 切换手动报警    K4(索引3) = 返回上级
    各分支先判断 state，再做光标移动或状态跳转，返回时同时设置好上级界面的光标位置。
    """
    global state, cursor, led8_mode, rgb_mode, alarm_threshold, manual_alarm
    if state == ST_MAIN:
        if 0 in kp:                        # K1 上移
            cursor = (cursor - 1) % 4
        elif 1 in kp:                      # K2 下移
            cursor = (cursor + 1) % 4
        elif 2 in kp:                      # K3 确定
            if cursor == 0:
                state = ST_STATUS
            elif cursor == 1:
                state = ST_LED
            elif cursor == 2:
                state = ST_NET
            elif cursor == 3:
                state = ST_BUZZER
            cursor = 0
        # K4 返回：主界面无操作
    elif state == ST_STATUS:
        if 3 in kp:                        # K4 返回
            state = ST_MAIN
            cursor = 0
    elif state == ST_LED:
        if 0 in kp:
            cursor = (cursor - 1) % 2
        elif 1 in kp:
            cursor = (cursor + 1) % 2
        elif 2 in kp:
            state = ST_LED8 if cursor == 0 else ST_RGB
            cursor = 0
        elif 3 in kp:
            state = ST_MAIN
            cursor = 1
    elif state == ST_LED8:
        if 0 in kp:
            cursor = (cursor - 1) % 3
        elif 1 in kp:
            cursor = (cursor + 1) % 3
        elif 2 in kp:                      # 确定，应用模式
            led8_mode = cursor
            state = ST_LED
            cursor = 0
        elif 3 in kp:
            state = ST_LED
            cursor = 0
    elif state == ST_RGB:
        if 0 in kp:
            cursor = (cursor - 1) % 3
        elif 1 in kp:
            cursor = (cursor + 1) % 3
        elif 2 in kp:                      # 确定，应用模式
            rgb_mode = cursor
            state = ST_LED
            cursor = 1
        elif 3 in kp:
            state = ST_LED
            cursor = 1
    elif state == ST_NET:
        if 3 in kp:
            state = ST_MAIN
            cursor = 2
    elif state == ST_BUZZER:
        if 0 in kp:                        # K1 增大阈值
            alarm_threshold = min(100, alarm_threshold + 1)
        elif 1 in kp:                      # K2 减小阈值
            alarm_threshold = max(2, alarm_threshold - 1)
        elif 2 in kp:                      # K3 切换手动报警
            manual_alarm = not manual_alarm
        elif 3 in kp:                      # K4 返回
            state = ST_MAIN
            cursor = 3

# -------------------- 创建MQTT连接 --------------------
# 连接 OneNET 云平台：CLIENT_ID 用设备名，NAME 用产品ID，PSWD 用工具生成的 token
client = MQTTClient(CLIENT_ID, SERVER, PORT, NAME, PSWD, 60)   # 60为心跳保活间隔(秒)
print('start connect...')
client.set_callback(MQTT_callback)     # 必须先注册回调，subscribe 内部会检查
client.connect()
print('success connect!')

# 订阅两个主题：上报回执(post/reply) 与 云端属性下发(set)
client.subscribe(post_Topic)
client.subscribe(subscribe_Topic)

# -------------------- 主循环 --------------------
# 采用"非阻塞分时调度"：为每个任务记录上次执行时刻，用运行时间差判断是否到期，
# 而不是用 time.sleep() 死等。这样各任务互不阻塞，即使某个任务耗时较长，
# 云端消息接收和按键响应也不会被拖延。
last_pub = time.ticks_ms()      # 传感器采集+上报 的上次执行时刻
last_led = time.ticks_ms()      # 灯光与蜂鸣器刷新 的上次执行时刻
last_oled = time.ticks_ms()     # OLED刷新 的上次执行时刻
last_check = time.ticks_ms()    # MQTT收消息 的上次执行时刻

while True:
    now = time.ticks_ms()

    # 按键处理（无固定周期，每轮都扫描，保证按键响应及时）
    kp = read_keys()
    if kp:
        handle_keys(kp)

    # LED动画与蜂鸣器（每30ms）
    if time.ticks_diff(now, last_led) >= 30:
        last_led = now
        update_leds()
        update_buzzer()

    # OLED刷新（每100ms）
    if time.ticks_diff(now, last_oled) >= 100:
        last_oled = now
        draw_current()

    # MQTT收取云端消息（每100ms）
    if time.ticks_diff(now, last_check) >= 100:
        last_check = now
        client.check_msg()

    # 传感器采集+发布（每1s）
    if time.ticks_diff(now, last_pub) >= 1000:
        last_pub = now
        update_light_auto()
        read_sensors_and_publish()

    # 短暂让出CPU，降低空转功耗，同时给WiFi/MQTT底层协议栈留出处理时间
    time.sleep_ms(10)

# -*- coding: utf-8 -*-
# ==============================================================================
# 项目名称：基于 ESP32 的环境检测与智能报警系统
# 课程名称：《物联网应用系统》课程设计
# 开发时间：2026-09
# 开发环境：ESP32-WROOM-32 + MicroPython + Thonny IDE
# ------------------------------------------------------------------------------
# 文件说明：ESP32 上电后自动运行的第一个文件（文件名固定为 boot.py，
#           由 MicroPython 固件在启动时自动调用，无需手动执行）。
# 功能简介：1. 关闭 ESP-IDF 底层调试日志，避免污染 Thonny 串口输出；
#           2. 创建 STA 模式并扫描、连接指定 WiFi 热点，
#              为 main.py 的 MQTT 通信提供网络能力；
#           3. 用 GPIO22 板载 LED 指示连接状态：
#              连接成功长亮，连接失败长灭（注意本板 LED 为低电平点亮，
#              因此 led.off() 表示亮、led.on() 表示灭）。
# ==============================================================================
from machine import Pin, I2C
import gc                              #内存回收
gc.collect()

#引用模块
import network
import time
import esp                             #用于关闭ESP-IDF底层调试日志
esp.osdebug(None)                      #关闭wifi等底层I(xxx)日志，避免污染串口(Thonny)

# led 22口，板载,同时通过扩展板引到右下角流水灯D8
led = Pin(22,Pin.OUT)                      # GPIO22 板载LED，与main.py中8路流水灯的D8共用一个引脚

# ==================== WiFi 连接函数 ====================
# 功能：扫描并连接指定热点，用板载LED指示连接状态
# 返回：无（连接结果通过串口打印和LED状态体现）
def wifi_conn():
    ssid_c='your_wifi_ssid'               #要接入热点的SSID
    password = 'your_wifi_password'       #热点密码
    
    #LED闪烁，开始连接WiFi
    led.off()                             #低电平点亮，off即亮
    time.sleep_ms(300)
    led.on()                              #高电平熄灭
    time.sleep_ms(300)
    
    wlan = network.WLAN(network.STA_IF)   # 创建STA模式（作为站点去连接路由器）
    wlan.active(True)                     # 激活网卡，不激活无法扫描/连接
        
    # 检测是否已经连接WiFi
    count=0                               #尝试连接10次
    if wlan.isconnected():
        led.off()                         #已连接：LED长亮
        print('\033[31m当前esp32已连接WiFi，ip地址：%s \033[0m'%(wlan.ifconfig()[0]))
    else:
        # 搜索WiFi
        print('搜索WiFi信号...')
        ssid_all = wlan.scan()     # 扫描附近的WiFi接入点，扫描的时候 定时器无法执行

        # 遍历扫描结果，确认目标热点是否存在，避免直接连接失败卡死
        get_ssid = 0
        for ssid in ssid_all:
            #print('%s\n'%str(bytes.decode(ssid[0])))
            if ssid_c == bytes.decode(ssid[0]):
                get_ssid = 1
        if get_ssid == 1:
            print('找到热点，准备连接。')
            # 连接WiFi
            try:
                wlan.connect(ssid_c,password)   # WiFi名，密码
                print('正在连接...',end="")                
                # 最多等待10秒，避免热点异常时程序无限阻塞
                while not wlan.isconnected() and count<10:  
                    print('.',end="")
                    time.sleep(1)
                    count += 1                
            except:
                led.on()                  #连接异常：LED长灭
                print('WiFi连接异常，请检查配置')
                sys.exit(-1)              #注意：需在文件开头 import sys 才能生效
            else:
                led.off()                 #连接成功：LED长亮
                print('\033[31m 已连接，WiFi名：%s IP地址：%s \033[0m'%(ssid_c,wlan.ifconfig()[0]))
        else:
            led.on()                      #未找到热点：LED长灭
            print('找不到WiFi热点,请检查热点是否开启。')

# 模块被加载时立即执行连接（boot.py由固件自动调用，无需 __main__ 判断）
wifi_conn()


# -*- coding: utf-8 -*-
# ==============================================================================
# 项目名称：基于 ESP32 的环境检测与智能报警系统
# 课程名称：《物联网应用系统》课程设计
# 开发时间：2026-09
# 开发环境：ESP32-WROOM-32 + MicroPython + Thonny IDE
# ------------------------------------------------------------------------------
# 文件说明：无源蜂鸣器单模块测试程序（课程实验例程，用于前期硬件验证）
# 功能简介：用 PWM 驱动接在 GPIO0 的无源蜂鸣器，循环播放两首简单乐曲，
#           用于验证蜂鸣器接线、发声频率与占空比是否正常，并可通过修改
#           音谱数组自行创作歌曲。
#           本文件不参与系统最终运行，主程序 main.py 中报警音固定用 2000Hz。
# ==============================================================================
from machine import Pin, PWM

from utime import sleep



ESP32TEST_Buzzer = 0             # 无源蜂鸣器管脚定义



# 音谱定义

Tone_CL = [0, 131, 147, 165, 175, 196, 211, 248]        # 低C音符的频率

Tone_CM = [0, 262, 294, 330, 350, 393, 441, 495]        # 中C音的频率

Tone_CH = [0, 525, 589, 661, 700, 786, 882, 990]        # 高C音符的频率





# 第一首歌音谱

ESP32TEST_song_1 = [ Tone_CM[3], Tone_CM[5], Tone_CM[6], Tone_CM[3], Tone_CM[2], Tone_CM[3], Tone_CM[5], Tone_CM[6],

                    Tone_CH[1], Tone_CM[6], Tone_CM[5], Tone_CM[1], Tone_CM[3], Tone_CM[2], Tone_CM[2], Tone_CM[3],

                    Tone_CM[5], Tone_CM[2], Tone_CM[3], Tone_CM[3], Tone_CL[6], Tone_CL[6], Tone_CL[6], Tone_CM[1],

                    Tone_CM[2], Tone_CM[3], Tone_CM[2], Tone_CL[7], Tone_CL[6], Tone_CM[1], Tone_CL[5] ]

# 第1首歌的节拍，1表示1/8拍

ESP32TEST_beat_1 = [ 1, 1, 3, 1, 1, 3, 1, 1,

                    1, 1, 1, 1, 1, 1, 3, 1,

                    1, 3, 1, 1, 1, 1, 1, 1,

                    1, 2, 1, 1, 1, 1, 1, 1,

                    1, 1, 3 ]

# 第二首歌音谱

ESP32TEST_song_2 = [ Tone_CM[1], Tone_CM[1], Tone_CM[1], Tone_CL[5], Tone_CM[3], Tone_CM[3], Tone_CM[3], Tone_CM[1],

                    Tone_CM[1], Tone_CM[3], Tone_CM[5], Tone_CM[5], Tone_CM[4], Tone_CM[3], Tone_CM[2], Tone_CM[2],

                    Tone_CM[3], Tone_CM[4], Tone_CM[4], Tone_CM[3], Tone_CM[2], Tone_CM[3], Tone_CM[1], Tone_CM[1],

                    Tone_CM[3], Tone_CM[2], Tone_CL[5], Tone_CL[7], Tone_CM[2], Tone_CM[1] ]



# 第2首歌的节拍，1表示1/8拍

ESP32TEST_beat_2 = [ 1, 1, 2, 2, 1, 1, 2, 2,

                    1, 1, 2, 2, 1, 1, 3, 1,

                    1, 2, 2, 1, 1, 2, 2, 1,

                    1, 2, 2, 1, 1, 3 ]



# GPIO设置函数

# 功能：初始化蜂鸣器 PWM 对象，上电时保持静音
def ESP32TEST_setup():

    global  buzzer

    # duty 取 512 约为 50% 占空比（范围 0~1023），占空比越大声音越响
    # freq 先设为 0 表示不发声，实际播放时由 playtone() 设置具体频率
    buzzer = PWM(Pin(ESP32TEST_Buzzer), freq=0, duty=512)  # 无源蜂鸣器管脚定义



# 播放音乐函数

# 功能：把发声频率设为 frequency(Hz)——无源蜂鸣器靠改变频率来发出不同音高
def playtone(frequency):

    buzzer.freq(frequency)





# 停止播放函数

# 功能：释放 PWM 资源，蜂鸣器停止发声
def bequiet():

    buzzer.deinit()



# 循环函数

def ESP32TEST_loop():

    while True:

        #    播放第一首歌音乐...

        for i in range(1, len(ESP32TEST_song_1)):     # 播放第一首歌

            playtone(ESP32TEST_song_1[i]) # 设置歌曲音符的频率

            sleep(ESP32TEST_beat_1[i] * 0.5) # 延迟一个节拍* 0.5秒的音符





        sleep(1)   # 等待下一首歌。



        #    播放第二首歌音乐...

        for i in range(1, len(ESP32TEST_song_2)):     # 播放第二首歌

            playtone(ESP32TEST_song_2[i]) # 设置歌曲音符的频率

            sleep(ESP32TEST_beat_2[i] * 0.5)     # 延迟一个节拍* 0.5秒的音符



        sleep(1)   # 等待下一首歌



# 程序入口

if __name__ == '__main__':

    ESP32TEST_setup()

    try:

        ESP32TEST_loop()

    except KeyboardInterrupt:  # 当按下Ctrl+C时，将执行destroy()子程序。

        bequiet()    # 停止播放


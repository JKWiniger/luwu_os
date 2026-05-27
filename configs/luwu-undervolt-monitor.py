#!/usr/bin/env python3
"""Luwu OS 电池电量读取（仅记录，不关机）"""
import subprocess, time

CHECK = 60
XGO = None

def log(msg):
    subprocess.run(["systemd-cat","-t","battery","-p","info"],
                   input=f"[battery] {msg}\n", text=True)

def init_xgo():
    global XGO
    from xgolib import XGO as X
    XGO = X("xgomini")
    log("机器人已连接")

def get_battery():
    global XGO
    if XGO is None:
        init_xgo()
    val = XGO.read_battery()
    if val is None or str(val).strip() == '' or val == 'Null':
        return None
    battery = int(val)
    # 0% 通常表示未连接机器狗或读取异常，不记录
    if battery <= 0:
        return None
    return battery

# ── 主循环 ──
try:
    init_xgo()
except Exception as e:
    log(f"机器人连接失败: {e}，将重试")

log("电池电量读取启动（仅记录，不关机）")

while True:
    try:
        battery = get_battery()
        if battery is not None:
            with open("/tmp/luwu_battery_level","w") as f:
                f.write(str(battery))
        time.sleep(CHECK)
    except Exception as e:
        log(f"循环异常: {e}")
        time.sleep(CHECK)

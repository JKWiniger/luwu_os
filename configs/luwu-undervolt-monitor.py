#!/usr/bin/env python3
"""Luwu OS 电池低电量关机监控"""
import subprocess, time, os

CHECK = 60
SHUTDOWN_THRESHOLD = 9
XGO = None

def log(msg):
    subprocess.run(["systemd-cat","-t","battery","-p","warning"],
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
    return int(XGO.read_battery())

def shutdown(reason):
    log(f"❌ {reason}，执行保护关机")
    subprocess.run(["wall", f"❌ {reason}，系统正在关机。请充电后重启。"])
    time.sleep(1)
    os.system("shutdown -h now '低电量保护'")

# ── 主循环 ──
try:
    init_xgo()
except Exception as e:
    log(f"机器人连接失败: {e}，将重试")

log("电池低电量关机监控启动")

while True:
    try:
        battery = get_battery()

        with open("/tmp/luwu_battery_level","w") as f:
            f.write(str(battery))

        if battery < SHUTDOWN_THRESHOLD:
            shutdown(f"电池仅{battery}%")

        time.sleep(CHECK)

    except Exception as e:
        log(f"循环异常: {e}")
        time.sleep(CHECK)

#!/usr/bin/env python3
"""Luwu OS 欠压+电池联合监控 — 分级响应"""
import subprocess, time, os

CHECK = 2
THRESHOLD = 5          # 10秒 / 2秒 = 5次
UV_COUNT = 0
XGO = None

def log(msg):
    subprocess.run(["systemd-cat","-t","undervolt","-p","warning"],
                   input=f"[undervolt] {msg}\n", text=True)

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

def get_uv():
    out = subprocess.check_output(["vcgencmd","get_throttled"], text=True)
    return int(out.strip().split("=")[-1], 16) & 0x1

def shutdown(reason):
    log(f"❌ {reason}，执行保护关机")
    subprocess.run(["wall", f"❌ {reason}，系统正在关机。更换电源后重启。"])
    time.sleep(1)
    os.system("shutdown -h now '欠压保护'")

# ── 主循环 ──
try:
    init_xgo()
except Exception as e:
    log(f"机器人连接失败: {e}，将重试")

log("欠压+电池联合监控启动 (分级响应)")

while True:
    try:
        battery = get_battery()
        uv = get_uv()

        if uv:
            UV_COUNT += 1
            elapsed = UV_COUNT * CHECK
            if UV_COUNT == 1:
                log(f"⚠ 欠压！电池={battery}%")
                with open("/tmp/luwu_undervolt_status","w") as f:
                    f.write("UNDERVOLT")

            if battery > 10:
                log(f"电池{battery}%>10%，忽略瞬时欠压")
                UV_COUNT = 0
            elif 5 <= battery <= 10:
                if UV_COUNT >= THRESHOLD:
                    shutdown(f"欠压{elapsed}秒+电池{battery}%")
                elif UV_COUNT == 2:
                    subprocess.run(["wall", f"⚠ 欠压{elapsed}秒，电池{battery}%。将持续监测。"])
            else:  # battery < 5
                shutdown(f"电池仅{battery}%")
        else:
            if UV_COUNT > 0:
                log("✓ 电压恢复")
            UV_COUNT = 0
            with open("/tmp/luwu_undervolt_status","w") as f:
                f.write("OK")

        with open("/tmp/luwu_battery_level","w") as f:
            f.write(str(battery))

        time.sleep(CHECK)

    except Exception as e:
        log(f"循环异常: {e}")
        time.sleep(CHECK)

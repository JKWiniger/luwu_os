#!/usr/bin/env python3
"""
luwu-os 硬件自动识别脚本 — CM4 新/老硬件自适应

逻辑:
  1. 非 CM4 → 直接退出 (CM5 无需处理)
  2. /dev/ttyAMA5 不存在 → 已是老硬件配置, 退出
  3. /dev/ttyAMA5 存在 → 发 xgolib 固件查询帧, 等回应
     - 有回应 → 新硬件, 保持配置, 退出
     - 无回应 → 老硬件, 复制 cm4-old.config → /boot/firmware/config.txt, 重启
"""

import os
import sys
import time
import shutil
import subprocess

CONFIGS_DIR = os.path.join(os.path.dirname(__file__))
NEW_CONFIG  = os.path.join(CONFIGS_DIR, "boot-config.txt")   # 新CM4/CM5 配置
OLD_CONFIG  = os.path.join(CONFIGS_DIR, "cm4-old.config")    # 老CM4 配置
BOOT_CONFIG = "/boot/firmware/config.txt"
PORT_NEW    = "/dev/ttyAMA5"   # 新CM4 机器狗串口
PORT_OLD    = "/dev/ttyAMA0"   # 老CM4 机器狗串口
BAUD        = 115200
LOG_FILE    = "/tmp/luwu_hw_autoconf.log"

# xgolib read_firmware 帧: addr=0x07, len=10
# tx = [0x55, 0x00, 0x09, 0x02, addr, read_len, checksum, 0x00, 0xAA]
# checksum = 255 - (0x09 + 0x02 + 0x07 + 0x0A) % 256 = 255 - 28 = 227
PROBE_FRAME = bytes([0x55, 0x00, 0x09, 0x02, 0x07, 0x0A, 0xE3, 0x00, 0xAA])


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def is_cm4() -> bool:
    try:
        with open("/proc/device-tree/model", "rb") as f:
            model = f.read().decode("utf-8", errors="replace").strip("\x00")
        return "Compute Module 4" in model
    except Exception:
        return False


def probe_port(port: str) -> bool:
    """向指定串口发 xgolib 固件查询帧, 返回 True 表示有回应"""
    try:
        import serial
        ser = serial.Serial(port, BAUD, timeout=0.6)
        ser.flushInput()
        ser.write(PROBE_FRAME)
        time.sleep(0.6)
        resp = ser.read(ser.in_waiting or 1)
        ser.close()
        log(f"{port} probe response ({len(resp)} bytes): {resp.hex() if resp else 'empty'}")
        return len(resp) > 0
    except PermissionError as e:
        # 端口被占用 → 说明已有进程在用, 可视为有设备
        log(f"{port} busy (PermissionError): {e} → treat as responded")
        return True
    except Exception as e:
        log(f"{port} probe error: {e}")
        return False


def switch_config(src: str) -> bool:
    if not os.path.exists(src):
        log(f"ERROR: {src} not found!")
        return False
    try:
        shutil.copy2(src, BOOT_CONFIG)
        log(f"Copied {src} → {BOOT_CONFIG}")
        return True
    except Exception as e:
        log(f"ERROR copy failed: {e}")
        return False


def reboot_after(sec: int = 2):
    log(f"Rebooting in {sec}s...")
    time.sleep(sec)
    subprocess.run(["reboot"], check=False)


def main():
    log("=== luwu hardware_autoconf start ===")

    if not is_cm4():
        log("Not CM4 (CM5 or other), exit")
        return

    log("CM4 detected")

    # ── 情况1/2: 当前是新硬件配置 (ttyAMA5 存在) ──────────────────
    if os.path.exists(PORT_NEW):
        log(f"{PORT_NEW} exists, probing...")
        if probe_port(PORT_NEW):
            log("New CM4 hardware confirmed (ttyAMA5 responded) ✓")
            return
        # ttyAMA5 无回应 → 老硬件误用了新配置
        log("No response on ttyAMA5 → old CM4 hardware on new config")
        if switch_config(OLD_CONFIG):
            reboot_after()
        else:
            log("Switch to old config failed — manual intervention required")
            sys.exit(1)
        return

    # ── 情况3/4: 当前是老硬件配置 (ttyAMA5 不存在) ────────────────
    log(f"{PORT_NEW} not found → on old-hardware config")
    if os.path.exists(PORT_OLD):
        log(f"{PORT_OLD} exists, probing...")
        if probe_port(PORT_OLD):
            log("Old CM4 hardware confirmed (ttyAMA0 responded) ✓")
            return
        # ttyAMA0 无回应 → 新硬件误用了老配置
        log("No response on ttyAMA0 → new CM4 hardware on old config")
    else:
        log(f"{PORT_OLD} not found either → assuming new CM4 hardware on old config")

    log("Switching back to new config (boot-config.txt) and rebooting...")
    if switch_config(NEW_CONFIG):
        reboot_after()
    else:
        log("Switch to new config failed — manual intervention required")
        sys.exit(1)


if __name__ == "__main__":
    main()

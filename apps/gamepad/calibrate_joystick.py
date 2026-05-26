#!/usr/bin/env python3
"""
2.4G Joystick 按键校准工具

逐个提示用户按手柄按键或推摇杆，每个步骤等待 5 秒，
记录实际 func_code，校准完成后自动更新 joystick_adapter.py。

运行前请先退出 gamepad 应用（否则会争抢 /dev/input/js0）。
"""

import os
import sys
import struct
import time
import select
import fcntl
import shutil

JS_PATH = "/dev/input/js0"
ADAPTER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "joystick_adapter.py")

# ── 待校准的按钮（名称 → 逻辑索引） ──
BUTTONS = [
    ("A",          0,  "按 A 键"),
    ("B",          1,  "按 B 键"),
    ("X",          2,  "按 X 键"),
    ("Y",          3,  "按 Y 键"),
    ("L1",         4,  "按 L1（左肩键）"),
    ("R1",         5,  "按 R1（右肩键）"),
    ("L2",         6,  "按 L2（左扳机）"),
    ("R2",         7,  "按 R2（右扳机）"),
    ("SELECT",     8,  "按 SELECT 键"),
    ("START",      9,  "按 START 键"),
    ("BTN_RK1",   10,  "按下左摇杆（L3）"),
    ("BTN_RK2",   11,  "按下右摇杆（R3）"),
    ("MODE",      16,  "按 MODE 键（如果有）"),
]

# ── 待校准的轴（名称 → 逻辑索引） ──
# 注意：十字键与左摇杆共用 axis num=0(左右) / num=1(上下)，无法分离
AXES = [
    ("RK1_LR", 0, "左摇杆 ← → 推到底"),
    ("RK1_UD", 1, "左摇杆 ↑ ↓ 推到底"),
    ("RK2_LR", 2, "右摇杆 ← → 推到底"),
    ("RK2_UD", 4, "右摇杆 ↑ ↓ 推到底"),
]


def open_js():
    if not os.path.exists(JS_PATH):
        print(f"\n❌ 未找到手柄设备 {JS_PATH}")
        print("   请确认 2.4G 接收器已插入，手柄已开机连接。")
        sys.exit(1)
    fd = os.open(JS_PATH, os.O_RDONLY)
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    return fd


def flush_events(fd, duration=0.3):
    """清空缓冲区中的旧事件"""
    deadline = time.time() + duration
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            try:
                os.read(fd, 8)
            except Exception:
                break
        else:
            break


def _decode_event(data):
    """解码 js_event 并返回 (raw_type, masked_type, value, number)"""
    _, value, etype, number = struct.unpack("IhBB", data)
    # JS_EVENT_INIT = 0x80，初始化事件的高位标记，需掩码掉
    masked = etype & 0x7F
    return etype, masked, value, number


def wait_for_button(fd, timeout=5.0):
    """等待按钮按下（masked_type=0x01, value=1），返回 func_code 或 None"""
    deadline = time.time() + timeout
    last_print = 0
    while time.time() < deadline:
        remaining = deadline - time.time()
        # 每秒打印倒计时
        now = time.time()
        if now - last_print >= 1.0:
            print(f"({int(remaining)}s) ", end="", flush=True)
            last_print = now
        r, _, _ = select.select([fd], [], [], min(0.2, remaining))
        if r:
            try:
                data = os.read(fd, 8)
                if len(data) == 8:
                    raw, masked, value, number = _decode_event(data)
                    print(f"[raw_type=0x{raw:02X} masked=0x{masked:02X} val={value} num={number}] ", end="", flush=True)
                    if masked == 0x01 and value == 1:
                        return (raw << 8) | number
            except BlockingIOError:
                pass
            except OSError:
                break
    return None


def wait_for_axis(fd, timeout=5.0):
    """等待轴事件（masked_type=0x02），返回 func_code 或 None"""
    deadline = time.time() + timeout
    last_print = 0
    while time.time() < deadline:
        remaining = deadline - time.time()
        now = time.time()
        if now - last_print >= 1.0:
            print(f"({int(remaining)}s) ", end="", flush=True)
            last_print = now
        r, _, _ = select.select([fd], [], [], min(0.2, remaining))
        if r:
            try:
                data = os.read(fd, 8)
                if len(data) == 8:
                    raw, masked, value, number = _decode_event(data)
                    print(f"[raw_type=0x{raw:02X} masked=0x{masked:02X} val={value} num={number}] ", end="", flush=True)
                    if masked == 0x02:
                        return (raw << 8) | number
            except BlockingIOError:
                pass
            except OSError:
                break
    return None


def update_adapter(btn_map, axis_map):
    """将校准结果写入 joystick_adapter.py"""
    # 备份原文件
    backup = ADAPTER_PATH + ".bak"
    if not os.path.exists(backup):
        shutil.copy2(ADAPTER_PATH, backup)
        print(f"📦 已备份原文件 → {backup}")

    with open(ADAPTER_PATH, 'r') as f:
        content = f.read()

    # ── JOYSTICK_BUTTON_MAP ──
    btn_lines = []
    for func, (name, idx) in sorted(btn_map.items()):
        btn_lines.append(f"    0x{func:04X}: {idx},   # {name}")
    new_btn_map = "JOYSTICK_BUTTON_MAP = {\n" + "\n".join(btn_lines) + "\n}"
    import re
    content = re.sub(
        r'JOYSTICK_BUTTON_MAP = \{.*?\}',
        new_btn_map,
        content, flags=re.DOTALL,
    )

    # ── JOYSTICK_AXIS_MAP ──
    axis_lines = []
    for func, (name, idx) in sorted(axis_map.items()):
        axis_lines.append(f"    0x{func:04X}: {idx},   # {name}")
    new_axis_map = "JOYSTICK_AXIS_MAP = {\n" + "\n".join(axis_lines) + "\n}"
    content = re.sub(
        r'JOYSTICK_AXIS_MAP = \{.*?\}',
        new_axis_map,
        content, flags=re.DOTALL,
    )

    # ── JOYSTICK_BUTTON_NAMES ──
    name_lines = []
    for func, (name, idx) in sorted(btn_map.items()):
        name_lines.append(f"    0x{func:04X}: \"{name}\",")
    new_names = "JOYSTICK_BUTTON_NAMES = {\n" + "\n".join(name_lines) + "\n}"
    content = re.sub(
        r'JOYSTICK_BUTTON_NAMES = \{.*?\}',
        new_names,
        content, flags=re.DOTALL,
    )

    # ── JOYSTICK_AXIS_NAMES ──
    ax_name_lines = []
    for func, (name, idx) in sorted(axis_map.items()):
        ax_name_lines.append(f"    0x{func:04X}: \"{name}\",")
    new_ax_names = "JOYSTICK_AXIS_NAMES = {\n" + "\n".join(ax_name_lines) + "\n}"
    content = re.sub(
        r'JOYSTICK_AXIS_NAMES = \{.*?\}',
        new_ax_names,
        content, flags=re.DOTALL,
    )

    with open(ADAPTER_PATH, 'w') as f:
        f.write(content)


def main():
    print()
    print("=" * 55)
    print("    2.4G Joystick 按键校准工具")
    print("=" * 55)
    print()
    print("请确保：")
    print("  1. 2.4G 接收器已插入机器狗")
    print("  2. gamepad 应用已退出")
    print("  3. 手柄已开机并完成配对（指示灯常亮）")
    print()
    input("按 Enter 开始校准...")

    fd = open_js()
    print(f"\n✅ 已打开 {JS_PATH}\n")

    btn_map = {}   # func_code → (name, logical_index)
    axis_map = {}  # func_code → (name, logical_index)

    # ========== 按钮校准 ==========
    print("─" * 45)
    print("  ① 按钮校准  (请依次按下对应按键)")
    print("─" * 45)

    for name, idx, desc in BUTTONS:
        input(f"\n  [{name}] {desc} - 按 Enter 开始计时...")
        flush_events(fd, 0.2)
        print(f"  [{name}] {desc} ", end="", flush=True)
        func = wait_for_button(fd, timeout=5.0)
        if func is not None:
            btn_map[func] = (name, idx)
            print(f"→  0x{func:04X}  ✅")
        else:
            print(f"→  超时跳过 ⏭️")

    # ========== 轴校准 ==========
    print()
    print("─" * 45)
    print("  ② 摇杆/轴校准  (请依次推动对应摇杆)")
    print("─" * 45)

    for name, idx, desc in AXES:
        input(f"\n  [{name}] {desc} - 按 Enter 开始计时...")
        flush_events(fd, 0.2)
        print(f"  [{name}] {desc} ", end="", flush=True)
        func = wait_for_axis(fd, timeout=5.0)
        if func is not None:
            axis_map[func] = (name, idx)
            print(f"→  0x{func:04X}  ✅")
        else:
            print(f"→  超时跳过 ⏭️")

    os.close(fd)

    # ========== 结果汇总 ==========
    print()
    print("=" * 55)
    print("  校准结果")
    print("=" * 55)

    print("\n  📌 按钮映射 (func_code → 名称):")
    for func, (name, idx) in sorted(btn_map.items()):
        print(f"      0x{func:04X}  →  {name}  (index={idx})")

    print("\n  📌 轴映射 (func_code → 名称):")
    for func, (name, idx) in sorted(axis_map.items()):
        print(f"      0x{func:04X}  →  {name}  (index={idx})")

    if not btn_map and not axis_map:
        print("\n❌ 没有校准到任何按键/轴，请检查手柄连接后重试。")
        sys.exit(1)

    # ========== 写入文件 ==========
    print()
    print("─" * 45)
    print("  写入 joystick_adapter.py ...")
    update_adapter(btn_map, axis_map)
    print(f"  ✅ 已更新 {ADAPTER_PATH}")
    print()
    print("  校准完成！现在可以启动 gamepad 应用测试了。")
    print()


if __name__ == "__main__":
    main()

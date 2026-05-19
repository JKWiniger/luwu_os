#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
luwu-os 设备探测脚本

职责：
- 输出当前机器人型号字符串到 stdout，仅一行。
  可能取值：xgomini / xgolite / xgomini2sw / xgorider / unknown
- 优先级：串口实时探测 > configs/device.ini 手动覆盖(fallback) > unknown
- 每次开机都重新串口探测，不再自动缓存，避免 SD 卡换机器后型号误判。
- device.ini 仅在串口探测失败时作为手动覆盖备选（用户自行创建）。
- stderr 用于日志，退出码 0 表示拿到了非 unknown 结果。

使用：
  python3 /home/pi/luwu-os/configs/detect_device.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

LUWU_ROOT = Path("/home/pi/luwu-os")
DEVICE_INI = LUWU_ROOT / "configs" / "device.ini"

VALID = {"xgomini", "xgolite", "xgomini2sw", "xgorider"}

# 串口扫描总超时（秒），避免阻塞 launcher 启动
SCAN_TIMEOUT_SEC = 1.5


def log(msg: str) -> None:
    print(f"[detect_device] {msg}", file=sys.stderr, flush=True)


def read_override() -> str | None:
    """读取 configs/device.ini 手动覆盖；返回合法值或 None。"""
    try:
        if not DEVICE_INI.exists():
            return None
        text = DEVICE_INI.read_text(encoding="utf-8").strip().lower()
        if text in VALID:
            return text
        if text:
            log(f"device.ini 内容非法: {text!r}，忽略")
        return None
    except Exception as e:
        log(f"读取 device.ini 失败: {e}")
        return None


def write_cache(dev: str) -> None:
    try:
        DEVICE_INI.parent.mkdir(parents=True, exist_ok=True)
        DEVICE_INI.write_text(dev + "\n", encoding="utf-8")
    except Exception as e:
        log(f"写入 device.ini 失败: {e}")


def firmware_to_device(fw: str) -> str:
    """固件首字母 → 设备类型，规则与 xgolib XGO() 内部保持一致。"""
    if not fw:
        return "unknown"
    if fw[0] == "R":
        return "xgorider"
    if fw[:2] == "MW" or fw[0] == "W":
        return "xgomini2sw"
    if fw[0] == "L":
        return "xgolite"
    if fw[0] == "M":
        return "xgomini"
    return "unknown"


def probe_serial() -> str:
    """通过 xgolib 实时扫描串口，超时返回 unknown。"""
    # 限制总超时：使用线程 + join 兜底（xgolib 本身可能阻塞较久）
    import threading
    import io

    sys.path.insert(0, str(LUWU_ROOT / "libs"))

    result: dict[str, str] = {"dev": "unknown", "fw": ""}

    def _do_probe() -> None:
        # 抑制 xgolib 内部 print 污染 stdout（launcher 只读取 stdout 最后一行作为 deviceId）
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                from xgolib import _scan_port  # type: ignore
            except Exception as e:
                log(f"导入 xgolib 失败: {e}")
                return
            try:
                port, fw = _scan_port(115200, verbose=False)
                result["fw"] = fw or ""
                result["dev"] = firmware_to_device(fw or "")
                log(f"扫描结果: port={port} fw={fw!r} -> {result['dev']}")
            except Exception as e:
                log(f"_scan_port 异常: {e}")

    th = threading.Thread(target=_do_probe, daemon=True)
    th.start()
    th.join(SCAN_TIMEOUT_SEC)
    if th.is_alive():
        log(f"探测超时 (>{SCAN_TIMEOUT_SEC}s)，返回 unknown")
        return "unknown"
    return result["dev"]


def main() -> int:
    # 1) 串口实时探测（每次开机重新检测，SD 卡换机器也不误判）
    dev = probe_serial()
    if dev in VALID:
        print(dev)
        return 0

    # 2) 串口探测失败，回退到 device.ini 手动覆盖
    override = read_override()
    if override:
        log(f"串口探测失败，使用 device.ini 手动覆盖: {override}")
        print(override)
        return 0

    # 3) 都失败
    print("unknown")
    return 1


if __name__ == "__main__":
    sys.exit(main())

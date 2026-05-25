#!/usr/bin/env python3
"""
Generic preload wrapper: imports PySide6 early, then blocks on a FIFO.
When the launcher writes an app path to the FIFO, that app is loaded and runs.

Protocol: launcher writes one line → "apps/demo_page/main.py"
"""
import sys
import os
import time
import importlib.util

FIFO_PATH = "/tmp/luwu_preload.fifo"
LUWU_ROOT = os.environ.get("LUWU_ROOT", "/opt/luwu-os")

t_start = time.monotonic()

# ---- Stage 1: preload PySide6 (shared by all apps) ----
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QKeyEvent, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout

t_import = (time.monotonic() - t_start) * 1000
print(f"[preload] PySide6 loaded in {t_import:.0f}ms", flush=True)

# ---- Stage 2: wait for launcher to tell us which app to run ----
print(f"[preload] waiting for target on {FIFO_PATH}...", flush=True)
with open(FIFO_PATH, 'r') as f:
    target = f.readline().strip()

t_wait = (time.monotonic() - t_start) * 1000
print(f"[preload] triggered after {t_wait:.0f}ms, target={target}", flush=True)

# ---- Stage 3: dynamically load and run the target app ----
if not target:
    print("[preload] no target specified, exiting", flush=True)
    sys.exit(1)

target_path = os.path.join(LUWU_ROOT, target)
if not os.path.exists(target_path):
    print(f"[preload] target not found: {target_path}", flush=True)
    sys.exit(1)

spec = importlib.util.spec_from_file_location("target_app", target_path)
mod = importlib.util.module_from_spec(spec)
sys.modules["target_app"] = mod
spec.loader.exec_module(mod)

print(f"[preload] {target} loaded, calling main()", flush=True)
mod.main()

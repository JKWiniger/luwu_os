#!/usr/bin/env python3
"""
Launcher 单张截图工具
用法: sudo python3 scripts/snap.py <名称>
示例: sudo python3 scripts/snap.py card_network
输出: screenshots/<名称>.png
"""

import struct
import sys
import os
from PIL import Image

FB_DEV = "/dev/fb0"
OUTPUT_DIR = "/opt/luwu-os/screenshots"
WIDTH, HEIGHT = 320, 240


def snap(name):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(FB_DEV, "rb") as f:
        raw = f.read()

    pixels = []
    for i in range(0, len(raw), 2):
        p = struct.unpack("<H", raw[i:i+2])[0]
        r = ((p >> 11) & 0x1F) << 3
        g = ((p >> 5) & 0x3F) << 2
        b = (p & 0x1F) << 3
        pixels.append((r, g, b))

    img = Image.new("RGB", (WIDTH, HEIGHT))
    img.putdata(pixels)

    path = os.path.join(OUTPUT_DIR, name + ".png")
    img.save(path, "PNG")
    print(f"✅ {path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: sudo python3 scripts/snap.py <名称>")
        sys.exit(1)
    snap(sys.argv[1])

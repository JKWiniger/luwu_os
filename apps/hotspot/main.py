#!/usr/bin/env python3
"""
PySide6 热点模式 App — 由 Luwu OS launcher 启动。
- 开放热点（无密码）
- 同一台设备首次创建后会持久化 SSID，下次进入直接复用，不再重新创建
- 左下角 C: 退出（保留热点）   右下角 D: 关闭热点
"""
import os
import sys
import time
import signal
import random
import string
import subprocess
import socket
import struct
import fcntl
from pathlib import Path

# ===================== 阶段计时 =====================
T0 = time.monotonic()


def mark(name: str):
    ms = (time.monotonic() - T0) * 1000.0
    print(f"[hotspot][+{ms:7.1f}ms] {name}", flush=True)


mark("python entry")

# ===================== PySide6 =====================
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QFrame

# ---- 主题层 ----
LUWU_ROOT = os.environ.get("LUWU_ROOT", "/opt/luwu-os")
if LUWU_ROOT not in sys.path:
    sys.path.insert(0, LUWU_ROOT)
from libs.theme import (  # noqa: E402
    apply_app_palette, Asset as T_Asset, Color as T_Color,
    Spacing, qss as T_qss,
)
from libs.ui import AppFrame  # noqa: E402

mark("PySide6 imports done")

# ===================== 常量 =====================
AUTO_EXIT_SEC = 300                       # 5 分钟自动退出页面（保留热点）
HOTSPOT_CONN_NAME = "LuwuHotspot"         # 固定连接名，便于复用
SSID_FILE = Path(LUWU_ROOT) / "configs" / "hotspot_ssid.txt"
WLAN_IFACE = "wlan0"
_LAUNCHER_ASSETS = os.path.dirname(T_Asset.bg_image)
DEMO_HOTSPOT_ICON = os.path.join(_LAUNCHER_ASSETS, "demo_hotspot.png")
_APP_BG_IMAGE = os.path.join(LUWU_ROOT, "assets/images/app_bg.png")


# ===================== 工具函数 =====================
def run_cmd(cmd: str, timeout: int = 30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return -1, "", str(e)


def get_ip(ifname: str = WLAN_IFACE) -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(
            fcntl.ioctl(s.fileno(), 0x8915, struct.pack("256s", bytes(ifname[:15], "utf-8")))[20:24]
        )
    except Exception:
        return ""


def gen_ssid() -> str:
    return "xgo-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def load_or_create_ssid() -> str:
    """读取已保存的 SSID；不存在时生成并写入。"""
    try:
        if SSID_FILE.exists():
            s = SSID_FILE.read_text().strip()
            if s:
                return s
    except Exception:
        pass
    s = gen_ssid()
    try:
        SSID_FILE.parent.mkdir(parents=True, exist_ok=True)
        SSID_FILE.write_text(s)
    except Exception:
        pass
    return s


def hotspot_is_active() -> bool:
    rc, out, _ = run_cmd("nmcli -t -f NAME,DEVICE connection show --active")
    for line in out.splitlines():
        if line.startswith(HOTSPOT_CONN_NAME + ":"):
            return True
    return False


def hotspot_conn_exists() -> bool:
    rc, out, _ = run_cmd("nmcli -t -f NAME connection show")
    return any(line.strip() == HOTSPOT_CONN_NAME for line in out.splitlines())


# ===================== UI =====================
class HotspotPage(AppFrame):
    def __init__(self):
        super().__init__()
        # 覆盖背景为 app_bg.png（与 settings / AI / rc_mode 同款）
        _pix = QPixmap(_APP_BG_IMAGE)
        if not _pix.isNull():
            self._bg_pix = _pix
            self.update()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._first_paint_logged = False

        self.ssid = ""
        self.ip_address = ""
        self.hotspot_active = False
        self._keep_hotspot_on_close = False

        # ---- 标题（AppFrame 提供） ----
        self.setTitle("热点模式")

        # ---- 中间主体：图标 + 装饰线 + SSID + IP + 状态 chip ----
        # 图标
        self.icon_label = QLabel(self)
        pix = QPixmap(DEMO_HOTSPOT_ICON)
        if not pix.isNull():
            self.icon_label.setPixmap(pix.scaled(
                88, 88,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet(T_qss.transparent())

        # accent 装饰线
        self.accent_line = QFrame(self)
        self.accent_line.setFixedSize(60, 2)
        self.accent_line.setStyleSheet(
            f"background-color: {T_Color.accent}; border: none;"
        )

        # SSID
        self.ssid_label = QLabel("", self)
        self.ssid_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ssid_label.setStyleSheet(T_qss.text("subtitle"))

        # IP
        self.ip_label = QLabel("", self)
        self.ip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ip_label.setStyleSheet(T_qss.text("body", color=T_Color.accent))

        # 状态 chip
        self.status_label = QLabel("正在启动...", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(T_qss.chip("muted"))

        # ---- 主布局（垂直居中）----
        center = QWidget(self)
        center.setStyleSheet(T_qss.transparent())
        v = QVBoxLayout(center)
        v.setContentsMargins(0, 0, 0, 0)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(Spacing.sm)
        v.addWidget(self.accent_line, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(Spacing.md)
        v.addWidget(self.ssid_label, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(Spacing.xs)
        v.addWidget(self.ip_label, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(Spacing.md)
        v.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignHCenter)
        self._center = center

        # ---- 角标 ----
        self.setCornerHints(
            bl=("退出", T_Asset.icon_back),
            br=("关闭热点", T_Asset.icon_enter),
        )

        QTimer.singleShot(AUTO_EXIT_SEC * 1000, self.close)
        QTimer.singleShot(200, self._init_hotspot)

    # ---- 布局事件 ----
    def resizeEvent(self, ev):
        super().resizeEvent(ev)  # AppFrame 负责背景与 4 角
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        top = max(28, h * 14 // 100)
        bottom = max(20, h * 8 // 100)
        self._center.setGeometry(0, top, w, h - top - bottom)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self._first_paint_logged:
            self._first_paint_logged = True
            mark("first paintEvent")

    # ---- 按键 ----
    def keyPressEvent(self, ev: QKeyEvent):
        key = ev.key()
        if key == Qt.Key.Key_Back:
            print("[hotspot] C -> close page, keep hotspot", flush=True)
            self._keep_hotspot_on_close = True
            self.close()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            print("[hotspot] D -> stop hotspot and exit", flush=True)
            self._stop_hotspot()
            self.close()

    # ---- 热点逻辑 ----
    def _init_hotspot(self):
        """启动入口：已激活则直接展示；否则创建/拉起。"""
        self.ssid = load_or_create_ssid()

        if hotspot_is_active():
            print(f"[hotspot] reuse active hotspot: {self.ssid}", flush=True)
            self.hotspot_active = True
            self.ip_address = get_ip() or "192.168.7.1"
            self._refresh_info("热点已就绪")
            return

        self._create_or_up_hotspot()

    def _create_or_up_hotspot(self):
        self.status_label.setText("正在创建热点...")
        QApplication.processEvents()

        run_cmd(f"sudo ifconfig {WLAN_IFACE} up")
        time.sleep(1)

        if hotspot_conn_exists():
            # 老 connection 可能残留了错误的 wifi-sec 字段（key-mgmt=none
            # 在 nmcli 中被识别为 WEP，导致 up 时报 "需要密钥" 错误），
            # 先移除整个 security 字段才是真正的开放热点。
            run_cmd(
                f"sudo nmcli connection modify {HOTSPOT_CONN_NAME} "
                f"remove 802-11-wireless-security 2>/dev/null"
            )
            rc, _, err = run_cmd(f"sudo nmcli connection up {HOTSPOT_CONN_NAME}")
            print(f"[hotspot] up existing rc={rc} err={err}", flush=True)
        else:
            # 清理旧的自动生成 Hotspot 残留（如 Hotspot-7）
            rc0, out0, _ = run_cmd("nmcli -t -f NAME connection show")
            for ln in out0.splitlines():
                n = ln.strip()
                if n.startswith("Hotspot") and n != HOTSPOT_CONN_NAME:
                    run_cmd(f"sudo nmcli connection delete '{n}' 2>/dev/null")

            run_cmd(f"sudo nmcli device disconnect {WLAN_IFACE} 2>/dev/null")
            time.sleep(1)
            # 不指定密码，不要设置 wifi-sec.key-mgmt（nmcli 中 none = WEP）。
            # 不带 security 字段 = 开放网络。
            run_cmd(
                f"sudo nmcli connection add type wifi ifname {WLAN_IFACE} "
                f"con-name {HOTSPOT_CONN_NAME} autoconnect no ssid {self.ssid}"
            )
            run_cmd(
                f"sudo nmcli connection modify {HOTSPOT_CONN_NAME} "
                f"802-11-wireless.mode ap 802-11-wireless.band bg "
                f"ipv4.method shared"
            )
            rc, _, err = run_cmd(f"sudo nmcli connection up {HOTSPOT_CONN_NAME}")
            print(f"[hotspot] up new rc={rc} err={err}", flush=True)

        time.sleep(2)
        # 以是否真的在活动连接里作为最终判断
        if hotspot_is_active():
            self.hotspot_active = True
            self.ip_address = get_ip() or "192.168.7.1"
            self._refresh_info("热点已就绪")
        else:
            self.hotspot_active = False
            self.ip_address = ""
            self.ssid_label.setText(f"SSID: {self.ssid}")
            self.ip_label.setText("")
            self.status_label.setText("热点启动失败")

    def _refresh_info(self, status_text: str):
        self.ssid_label.setText(f"SSID: {self.ssid}")
        self.ip_label.setText(f"IP: {self.ip_address}")
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(T_qss.chip("success"))

    def _stop_hotspot(self):
        print("[hotspot] stopping hotspot...", flush=True)
        run_cmd(f"sudo nmcli connection down {HOTSPOT_CONN_NAME} 2>/dev/null")

    def closeEvent(self, ev):
        print(f"[hotspot] closing (keep={self._keep_hotspot_on_close})", flush=True)
        if self.hotspot_active and not self._keep_hotspot_on_close:
            self._stop_hotspot()
        super().closeEvent(ev)


# ===================== 入口 =====================
def main():
    signal.signal(signal.SIGINT, lambda *_: QApplication.instance().quit())
    signal.signal(signal.SIGTERM, lambda *_: QApplication.instance().quit())

    app = QApplication(sys.argv)
    apply_app_palette(app)
    mark("QApplication created")

    w = HotspotPage()
    mark("widget constructed")

    w.showFullScreen()
    mark("showFullScreen returned")

    rc = app.exec()
    print(f"[hotspot] exit rc={rc}", flush=True)
    sys.exit(rc)


if __name__ == "__main__":
    main()

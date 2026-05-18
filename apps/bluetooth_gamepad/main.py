#!/usr/bin/env python3
"""
PySide6 蓝牙遥控 App — 由 Luwu OS launcher 启动。

功能：
- 自动开启蓝牙、扫描周围手柄设备
- 自动配对 + 信任 + 连接（Xbox / Wireless Controller / Gamepad 等）
- 已连接的手柄会优先复用，无需重新配对
- 连接成功后自动启动 evdev 手柄控制器，实时操控机器狗
- 断开自动重连

按键：
- C 键（Key_Back）：退出
- D 键（Key_Return）：手动重新扫描
"""
import os
import sys
import re
import time
import signal
import subprocess
import threading

# ===================== 阶段计时 =====================
T0 = time.monotonic()


def mark(name: str):
    ms = (time.monotonic() - T0) * 1000.0
    print(f"[bt_gamepad][+{ms:7.1f}ms] {name}", flush=True)


mark("python entry")

# ===================== PySide6 =====================
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QFrame

# ---- luwu-os 主题层 ----
if "/home/pi/luwu-os" not in sys.path:
    sys.path.insert(0, "/home/pi/luwu-os")
from libs.theme import (  # noqa: E402
    apply_app_palette, Asset as T_Asset, Color as T_Color,
    Spacing, qss as T_qss,
)
from libs.ui import AppFrame  # noqa: E402
from libs.i18n import Translator as _Translator  # noqa: E402

mark("PySide6 imports done")

# ===================== i18n =====================
_T = _Translator({
    "cn": {
        "title": "蓝牙遥控",
        "init": "正在初始化蓝牙...",
        "scanning": "正在扫描蓝牙手柄...",
        "pairing": "正在配对：{}",
        "connecting": "正在连接：{}",
        "connected": "已连接：{}",
        "ready": "手柄就绪，正在控制机器狗",
        "already": "手柄已连接",
        "disconnected": "手柄已断开，重新扫描中...",
        "not_found": "未发现手柄，{} 秒后重试",
        "pair_failed": "配对失败，重试中...",
        "connect_failed": "连接失败，重试中...",
        "bt_error": "蓝牙未就绪",
        "hint_exit": "退出",
        "hint_rescan": "重新扫描",
    },
    "en": {
        "title": "BT Gamepad",
        "init": "Initializing Bluetooth...",
        "scanning": "Scanning for gamepad...",
        "pairing": "Pairing: {}",
        "connecting": "Connecting: {}",
        "connected": "Connected: {}",
        "ready": "Gamepad ready, controlling robot",
        "already": "Gamepad already connected",
        "disconnected": "Disconnected, rescanning...",
        "not_found": "No gamepad found, retry in {}s",
        "pair_failed": "Pair failed, retrying...",
        "connect_failed": "Connect failed, retrying...",
        "bt_error": "Bluetooth not ready",
        "hint_exit": "Exit",
        "hint_rescan": "Rescan",
    },
})

# ===================== 常量 =====================
AUTO_EXIT_SEC = 1800  # 30 分钟无输入自动退出
GAMEPAD_KEYWORDS = [
    "xbox", "microsoft",
    "wireless controller", "pro controller",
    "gamepad", "controller",
    "8bitdo", "joystick",
    "tl_",        # 天龙/腾龙系列: TL_0002E13CC2067322 等
    "gp",         # 部分国产手柄前缀
    "ipega", "betop", "flydigi", "razer", "dualsense", "dualshock",
]
SCAN_DURATION = 10       # 单次扫描时长（秒）
SCAN_RETRY_INTERVAL = 5  # 未找到设备的重试间隔（秒）
MAX_SCAN_RETRY = 12      # 最大重试次数

_LAUNCHER_ASSETS = os.path.dirname(T_Asset.bg_image)
DEMO_ICON = os.path.join(_LAUNCHER_ASSETS, "demo_gamepad.png")
_APP_BG_IMAGE = "/home/pi/luwu-os/assets/images/app_bg.png"


# ===================== 工具函数 =====================
def run_cmd(cmd: str, timeout: int = 12):
    """执行 shell 命令，返回 (rc, stdout, stderr)"""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def bt_setup():
    """初始化蓝牙：开机 + 配对代理 + 可被发现/可被配对"""
    run_cmd("bluetoothctl power on")
    run_cmd("bluetoothctl pairable on")
    run_cmd("bluetoothctl agent NoInputNoOutput")
    run_cmd("bluetoothctl default-agent")


def bt_is_powered() -> bool:
    rc, out, _ = run_cmd("bluetoothctl show")
    return "Powered: yes" in out


def bt_list_devices():
    """返回 [(mac, name), ...] —— 已知 + 已扫描到的所有设备"""
    rc, out, _ = run_cmd("bluetoothctl devices")
    items = []
    for line in out.splitlines():
        m = re.match(r"Device\s+([0-9A-Fa-f:]{17})\s+(.+)", line.strip())
        if m:
            items.append((m.group(1), m.group(2).strip()))
    return items


def bt_info(mac: str) -> str:
    """返回 bluetoothctl info <mac> 的完整输出"""
    _, out, _ = run_cmd(f"bluetoothctl info {mac}")
    return out


def bt_is_gaming_device(mac: str) -> bool:
    """通过 Icon / Class 判断是否为游戏手柄（名字过滤失败时的兜底检测）"""
    info = bt_info(mac)
    # Icon: input-gaming  → 明确是手柄/游戏输入设备
    if "Icon: input-gaming" in info:
        return True
    # Bluetooth Class 低字节：Major=Peripheral(0x05), Minor=Gamepad(0x08) → Class 末位含 0x508
    m = re.search(r"Class:\s+0x([0-9a-fA-F]+)", info)
    if m:
        cls = int(m.group(1), 16)
        major = (cls >> 8) & 0x1F
        minor = (cls >> 2) & 0x3F
        if major == 5 and minor in (4, 8):  # Joystick / Gamepad
            return True
    return False


def bt_is_connected(mac: str) -> bool:
    return "Connected: yes" in bt_info(mac)


def bt_is_paired(mac: str) -> bool:
    return "Paired: yes" in bt_info(mac)


def bt_pair(mac: str) -> bool:
    rc, out, err = run_cmd(f"bluetoothctl pair {mac}", timeout=20)
    txt = (out + err).lower()
    return rc == 0 or "successful" in txt or "already" in txt


def bt_trust(mac: str) -> bool:
    rc, _, _ = run_cmd(f"bluetoothctl trust {mac}")
    return rc == 0


def bt_connect(mac: str) -> bool:
    rc, out, err = run_cmd(f"bluetoothctl connect {mac}", timeout=15)
    txt = (out + err).lower()
    return rc == 0 or "successful" in txt


def bt_scan(duration: int = SCAN_DURATION):
    """扫描指定时长后自动退出（bluez 5.x 的 --timeout 选项）"""
    run_cmd(f"bluetoothctl --timeout {duration} scan on", timeout=duration + 5)


def is_gamepad_name(name: str) -> bool:
    """通过名字快速判断是否可能是手柄"""
    if not name:
        return False
    low = name.lower()
    return any(kw in low for kw in GAMEPAD_KEYWORDS)


def find_gamepads():
    """返回当前已知设备里的所有手柄 [(mac, name, connected), ...]
    双重检测：先按名字关键词匹配，不命中再查询蓝牙设备 Class/Icon"""
    result = []
    for mac, name in bt_list_devices():
        if is_gamepad_name(name):
            result.append((mac, name, bt_is_connected(mac)))
        elif bt_is_gaming_device(mac):
            # 名字没匹配但设备类型是 input-gaming
            result.append((mac, name, bt_is_connected(mac)))
    return result


# ===================== BT 后台线程 =====================
class BTWorker(QThread):
    """后台线程：扫描、自动配对、自动连接、断线重连"""

    status_changed = Signal(str, str)   # (key, detail)
    gamepad_ready = Signal(str, str)    # (mac, name) — 手柄已就绪可控制
    gamepad_lost = Signal()             # 手柄断开

    def __init__(self):
        super().__init__()
        self._running = True
        self._force_rescan = False

    def stop(self):
        self._running = False

    def request_rescan(self):
        self._force_rescan = True

    # ---- 主流程 ----
    def run(self):
        # 1. 初始化蓝牙
        self.status_changed.emit("init", "")
        bt_setup()
        if not bt_is_powered():
            self.status_changed.emit("bt_error", "")
            return

        # 2. 主循环：连 → 维持 → 断 → 重扫
        while self._running:
            # 2.1 优先复用已连接的手柄
            mac, name = self._find_connected()
            if mac:
                self.status_changed.emit("already", name)
                self.gamepad_ready.emit(mac, name)
                self._monitor(mac, name)
                if not self._running:
                    break
                continue

            # 2.2 扫描 + 配对 + 连接
            ok = self._scan_and_connect()
            if not ok and self._running:
                # 连续多次失败，停顿一段时间后重试
                for _ in range(3):
                    if not self._running or self._force_rescan:
                        break
                    time.sleep(1)
                self._force_rescan = False

    def _find_connected(self):
        for mac, name, connected in find_gamepads():
            if connected:
                return mac, name
        return None, None

    def _scan_and_connect(self) -> bool:
        retry = 0
        while self._running and retry < MAX_SCAN_RETRY:
            self._force_rescan = False

            self.status_changed.emit("scanning", "")
            bt_scan(SCAN_DURATION)
            if not self._running:
                return False

            gamepads = find_gamepads()
            # 已连接的优先（极少见，但保险）
            for mac, name, conn in gamepads:
                if conn:
                    self.status_changed.emit("connected", name)
                    self.gamepad_ready.emit(mac, name)
                    self._monitor(mac, name)
                    return True

            # 未连接的尝试配对 + 连接
            for mac, name, _ in gamepads:
                if not self._running:
                    return False
                if self._try_pair_connect(mac, name):
                    self._monitor(mac, name)
                    return True

            retry += 1
            remaining = max(1, MAX_SCAN_RETRY - retry)
            self.status_changed.emit("not_found", str(SCAN_RETRY_INTERVAL))
            for _ in range(SCAN_RETRY_INTERVAL):
                if not self._running or self._force_rescan:
                    break
                time.sleep(1)
            if self._force_rescan:
                retry = 0

        return False

    def _try_pair_connect(self, mac: str, name: str) -> bool:
        # 已配对则跳过 pair
        if not bt_is_paired(mac):
            self.status_changed.emit("pairing", name)
            if not bt_pair(mac):
                self.status_changed.emit("pair_failed", name)
                time.sleep(1)
                return False
            bt_trust(mac)
            time.sleep(1)

        self.status_changed.emit("connecting", name)
        if not bt_connect(mac):
            self.status_changed.emit("connect_failed", name)
            time.sleep(1)
            return False

        # 连接结果验证
        for _ in range(5):
            if bt_is_connected(mac):
                self.status_changed.emit("connected", name)
                self.gamepad_ready.emit(mac, name)
                return True
            time.sleep(0.5)

        self.status_changed.emit("connect_failed", name)
        return False

    def _monitor(self, mac: str, name: str):
        """连接成功后监控掉线"""
        while self._running and not self._force_rescan:
            time.sleep(3)
            if not bt_is_connected(mac):
                self.status_changed.emit("disconnected", name)
                self.gamepad_lost.emit()
                time.sleep(2)
                return


# ===================== 控制器线程 =====================
class ControllerThread(threading.Thread):
    """后台运行 libs/gamepad_config/gamepad_controller.py 中的 XGOController"""

    def __init__(self):
        super().__init__(daemon=True, name="xgo-gamepad-ctrl")
        self._controller = None

    def run(self):
        try:
            gp_dir = "/home/pi/luwu-os/libs/gamepad_config"
            if gp_dir not in sys.path:
                sys.path.insert(0, gp_dir)
            import gamepad_controller as gc
            # 强制纠正 CONFIG_FILE 路径（原文件含历史遗留错误）
            gc.CONFIG_FILE = os.path.join(gp_dir, "mappings.json")
            self._controller = gc.XGOController()
            self._controller.run()
        except Exception as e:
            print(f"[bt_gamepad] controller error: {e}", flush=True)

    def stop(self):
        c = self._controller
        if not c:
            return
        try:
            c._running = False
            c._stop_movement()
        except Exception:
            pass


# ===================== UI =====================
class BTGamepadPage(AppFrame):
    def __init__(self):
        super().__init__()
        # 与 settings/AI/hotspot 同款应用背景
        _pix = QPixmap(_APP_BG_IMAGE)
        if not _pix.isNull():
            self._bg_pix = _pix
            self.update()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._first_paint_logged = False

        self._bt_worker: BTWorker | None = None
        self._ctrl_thread: ControllerThread | None = None

        # ---- 标题 ----
        self.setTitle(_T("title"))

        # ---- 图标 ----
        self.icon_label = QLabel(self)
        pix = QPixmap(DEMO_ICON)
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

        # 设备名
        self.device_label = QLabel("", self)
        self.device_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.device_label.setStyleSheet(T_qss.text("subtitle"))

        # 状态 chip
        self.status_label = QLabel(_T("init"), self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(T_qss.chip("muted"))

        # 子状态（控制器是否启动）
        self.sub_label = QLabel("", self)
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setStyleSheet(T_qss.text("body", color=T_Color.accent))

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
        v.addWidget(self.device_label, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(Spacing.xs)
        v.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(Spacing.xs)
        v.addWidget(self.sub_label, 0, Qt.AlignmentFlag.AlignHCenter)
        self._center = center

        # ---- 角标 ----
        self.setCornerHints(
            bl=(_T("hint_exit"), T_Asset.icon_back),
            br=(_T("hint_rescan"), T_Asset.icon_enter),
        )

        QTimer.singleShot(AUTO_EXIT_SEC * 1000, self.close)
        QTimer.singleShot(200, self._start_bt)

    # ---- 布局 ----
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
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

    # ---- BT worker 启停 ----
    def _start_bt(self):
        if self._bt_worker and self._bt_worker.isRunning():
            return
        self._bt_worker = BTWorker()
        self._bt_worker.status_changed.connect(self._on_status)
        self._bt_worker.gamepad_ready.connect(self._on_ready)
        self._bt_worker.gamepad_lost.connect(self._on_lost)
        self._bt_worker.start()

    # ---- 状态更新 ----
    def _on_status(self, key: str, detail: str):
        muted = T_qss.chip("muted")
        success = T_qss.chip("success")

        if key == "init":
            self.device_label.setText("")
            self.status_label.setText(_T("init"))
            self.status_label.setStyleSheet(muted)
        elif key == "scanning":
            self.device_label.setText("")
            self.status_label.setText(_T("scanning"))
            self.status_label.setStyleSheet(muted)
        elif key == "pairing":
            self.device_label.setText(detail)
            self.status_label.setText(_T("pairing", detail))
            self.status_label.setStyleSheet(muted)
        elif key == "connecting":
            self.device_label.setText(detail)
            self.status_label.setText(_T("connecting", detail))
            self.status_label.setStyleSheet(muted)
        elif key == "connected":
            self.device_label.setText(detail)
            self.status_label.setText(_T("connected", detail))
            self.status_label.setStyleSheet(success)
        elif key == "already":
            self.device_label.setText(detail)
            self.status_label.setText(_T("already"))
            self.status_label.setStyleSheet(success)
        elif key == "disconnected":
            self.sub_label.setText("")
            self.device_label.setText("")
            self.status_label.setText(_T("disconnected"))
            self.status_label.setStyleSheet(muted)
        elif key == "not_found":
            self.device_label.setText("")
            self.status_label.setText(_T("not_found", detail))
            self.status_label.setStyleSheet(muted)
        elif key == "pair_failed":
            self.status_label.setText(_T("pair_failed"))
            self.status_label.setStyleSheet(muted)
        elif key == "connect_failed":
            self.status_label.setText(_T("connect_failed"))
            self.status_label.setStyleSheet(muted)
        elif key == "bt_error":
            self.status_label.setText(_T("bt_error"))
            self.status_label.setStyleSheet(muted)

    def _on_ready(self, mac: str, name: str):
        """手柄连接就绪 → 启动控制器"""
        self._start_controller()
        self.sub_label.setText(_T("ready"))

    def _on_lost(self):
        """手柄断开 → 停止控制器"""
        self._stop_controller()
        self.sub_label.setText("")

    # ---- 控制器启停 ----
    def _start_controller(self):
        if self._ctrl_thread and self._ctrl_thread.is_alive():
            return
        self._ctrl_thread = ControllerThread()
        self._ctrl_thread.start()
        print("[bt_gamepad] controller started", flush=True)

    def _stop_controller(self):
        if self._ctrl_thread and self._ctrl_thread.is_alive():
            self._ctrl_thread.stop()
        self._ctrl_thread = None
        print("[bt_gamepad] controller stopped", flush=True)

    # ---- 按键 ----
    def keyPressEvent(self, ev: QKeyEvent):
        key = ev.key()
        if key == Qt.Key.Key_Back:
            print("[bt_gamepad] C -> exit", flush=True)
            self.close()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            print("[bt_gamepad] D -> rescan", flush=True)
            self._stop_controller()
            if self._bt_worker:
                self._bt_worker.request_rescan()
            else:
                self._start_bt()

    # ---- 退出清理 ----
    def closeEvent(self, ev):
        print("[bt_gamepad] closing", flush=True)
        self._stop_controller()
        if self._bt_worker:
            self._bt_worker.stop()
            self._bt_worker.quit()
            self._bt_worker.wait(3000)
            self._bt_worker = None
        # 收尾：停止扫描，避免后台一直耗电
        run_cmd("bluetoothctl scan off", timeout=3)
        super().closeEvent(ev)


# ===================== 入口 =====================
def main():
    signal.signal(signal.SIGINT, lambda *_: QApplication.instance().quit())
    signal.signal(signal.SIGTERM, lambda *_: QApplication.instance().quit())

    app = QApplication(sys.argv)
    apply_app_palette(app)
    mark("QApplication created")

    w = BTGamepadPage()
    mark("widget constructed")

    w.showFullScreen()
    mark("showFullScreen returned")

    rc = app.exec()
    print(f"[bt_gamepad] exit rc={rc}", flush=True)
    sys.exit(rc)


if __name__ == "__main__":
    main()

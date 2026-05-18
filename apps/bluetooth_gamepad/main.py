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
import select
import subprocess
import threading
import pty

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


# ===================== 持久化 bluetoothctl 会话 =====================
class BtSession:
    """维护一个持久 bluetoothctl 进程，保证 agent 注册不丢失
    
    关键：bluetoothctl 的 agent 命令需要进程保持运行才能维护 D-Bus 对象。
    之前每次 subprocess.run 都会让进程退出 → agent 注销 → 配对失败。
    这个类用一个 Popen 进程一直活着，所有命令通过 stdin 发送。
    """

    def __init__(self):
        self._proc = None
        self._lock = threading.Lock()
        self._ready = False

    # ── 启动 / 停止 ──────────────────────────────────────────────

    def start(self):
        print("[bt_gamepad] starting persistent bluetoothctl session (pty)...", flush=True)
        # 用 PTY 让 bluetoothctl 认为自己是交互式终端 —— 否则 buffering 会卡死
        self._master_fd, slave_fd = pty.openpty()
        self._proc = subprocess.Popen(
            ["bluetoothctl"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
        os.close(slave_fd)
        # 先标记 alive 让 _send 能通过
        self._ready = True
        # 等待 bluetoothctl 启动并出现提示符
        self._read_until(8)
        # 初始设置
        self._send("power on", 5)
        self._send("pairable on", 5)
        out = self._send("agent NoInputNoOutput", 5)
        print(f"[bt_gamepad] agent: {out.strip()[:150]}", flush=True)
        if "Failed" in out or "fail" in out.lower():
            print("[bt_gamepad] !! agent register FAILED", flush=True)
            self._ready = False
        else:
            print("[bt_gamepad] agent registered OK", flush=True)
        self._send("default-agent", 5)
        print("[bt_gamepad] BtSession ready", flush=True)

    def stop(self):
        self._ready = False
        if hasattr(self, '_master_fd') and self._master_fd is not None:
            try:
                os.write(self._master_fd, b"scan off\nquit\n")
            except Exception:
                pass
            try:
                os.close(self._master_fd)
            except Exception:
                pass
            self._master_fd = None
        if self._proc:
            try:
                self._proc.wait(timeout=3)
            except Exception:
                self._proc.kill()
            self._proc = None
            print("[bt_gamepad] BtSession stopped", flush=True)

    def is_alive(self):
        return self._ready and self._proc and self._proc.poll() is None

    # ── 底层通信（PTY 读写）───────────────────────────────────

    def _read_until(self, timeout=8, idle=0.5, wait_for=None):
        """读取输出。
        - 普通命令：连续读取，遇到 idle 秒没新数据就返回。
        - 慢命令(pair/connect)：传入 wait_for=["successful","failed"] 等关键词，
          只有匹配到关键词 或 超时 才返回，中间的静默不会提前退出。
        """
        buf = ""
        deadline = time.time() + timeout
        last_data = time.time()
        while time.time() < deadline:
            r, _, _ = select.select([self._master_fd], [], [], 0.1)
            if r:
                try:
                    chunk = os.read(self._master_fd, 4096).decode("utf-8", errors="replace")
                except Exception:
                    break
                if chunk:
                    buf += chunk
                    last_data = time.time()
                    # 如果有关键词等待，检查是否命中
                    if wait_for:
                        low = buf.lower()
                        if any(kw in low for kw in wait_for):
                            break
            else:
                # 没新数据，检查静默期（仅在无 wait_for 时使用）
                if not wait_for and buf and (time.time() - last_data) > idle:
                    break
        return buf

    def _send(self, cmd: str, timeout=8, idle=0.5, wait_for=None):
        """发送命令，返回完整输出。wait_for: 关键词列表，命中才返回。"""
        with self._lock:
            if not self.is_alive():
                print(f"[bt_gamepad] !! session dead, skip: {cmd}", flush=True)
                return ""
            print(f"[bt_gamepad] BT> {cmd}", flush=True)
            try:
                os.write(self._master_fd, (cmd + "\n").encode())
            except Exception as e:
                print(f"[bt_gamepad] !! write error: {e}", flush=True)
                return ""
            out = self._read_until(timeout, idle, wait_for=wait_for)
            # 精简输出
            for line in out.strip().splitlines():
                line = line.strip()
                if line and "[bluetoothctl]" not in line and not line.startswith("\x1b"):
                    print(f"[bt_gamepad] BT< {line[:200]}", flush=True)
            return out

    # ── 高级操作 ──────────────────────────────────────────────────

    def show(self):
        return self._send("show", 5)

    def devices(self):
        return self._send("devices", 5)

    def info(self, mac: str):
        return self._send(f"info {mac}", 5)

    def scan(self, duration: int = SCAN_DURATION):
        """扫描指定时长后关闭"""
        # 启动扫描（不等待输出完）
        self._send("scan on", timeout=2, idle=0.3)
        # 扫描期间持锁后台消费 stdout，避免后续命令读到脱起的扫描输出
        with self._lock:
            deadline = time.time() + duration
            while time.time() < deadline:
                r, _, _ = select.select([self._master_fd], [], [], 0.5)
                if r:
                    try:
                        os.read(self._master_fd, 4096)
                    except Exception:
                        break
        self._send("scan off", timeout=2, idle=0.3)

    def pair(self, mac: str, timeout=20):
        return self._send(f"pair {mac}", timeout,
                          wait_for=["pairing successful", "failed to pair",
                                    "already exists", "not available"])

    def trust(self, mac: str):
        return self._send(f"trust {mac}", 5)

    def connect(self, mac: str, timeout=15):
        return self._send(f"connect {mac}", timeout,
                          wait_for=["connection successful", "failed to connect",
                                    "already connected", "not available"])


# 全局单例
_bt = BtSession()


# ===================== 工具函数（基于 BtSession）=====================

def bt_setup():
    """初始化蓝牙会话（启动持久进程）"""
    if not _bt.is_alive():
        _bt.start()

def bt_is_powered() -> bool:
    return "Powered: yes" in _bt.show()

def bt_list_devices():
    """返回 [(mac, name), ...]"""
    out = _bt.devices()
    items = []
    for line in out.splitlines():
        m = re.match(r"Device\s+([0-9A-Fa-f:]{17})\s+(.+)", line.strip())
        if m:
            items.append((m.group(1), m.group(2).strip()))
    return items

def bt_info(mac: str) -> str:
    return _bt.info(mac)

def bt_is_gaming_device(mac: str) -> bool:
    info = bt_info(mac)
    if "Icon: input-gaming" in info:
        return True
    m = re.search(r"Class:\s+0x([0-9a-fA-F]+)", info)
    if m:
        cls = int(m.group(1), 16)
        major = (cls >> 8) & 0x1F
        minor = (cls >> 2) & 0x3F
        if major == 5 and minor in (4, 8):
            return True
    return False

def bt_is_connected(mac: str) -> bool:
    return "Connected: yes" in bt_info(mac)

def bt_is_paired(mac: str) -> bool:
    return "Paired: yes" in bt_info(mac)

def bt_pair(mac: str) -> bool:
    out = _bt.pair(mac, timeout=20)
    txt = out.lower()
    return "successful" in txt or "already" in txt

def bt_trust(mac: str) -> bool:
    out = _bt.trust(mac)
    return "succeeded" in out.lower() or "Changing" in out

def bt_connect(mac: str) -> bool:
    out = _bt.connect(mac, timeout=15)
    txt = out.lower()
    return "successful" in txt or "already" in txt

def bt_scan(duration: int = SCAN_DURATION):
    _bt.scan(duration)

def is_gamepad_name(name: str) -> bool:
    if not name:
        return False
    low = name.lower()
    return any(kw in low for kw in GAMEPAD_KEYWORDS)

def find_gamepads():
    """返回当前已知设备里的所有手柄 [(mac, name, connected), ...]"""
    result = []
    for mac, name in bt_list_devices():
        if is_gamepad_name(name):
            result.append((mac, name, bt_is_connected(mac)))
        elif bt_is_gaming_device(mac):
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
        # 停止持久 bluetoothctl 会话
        _bt.stop()
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

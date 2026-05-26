#!/usr/bin/env python3
"""
PySide6 2.4G 遥控 — Luwu OS 统一手柄控制。
使用 gamepad_controller 读取 evdev 手柄设备，控制 XGO 机器狗。

与蓝牙页面共享同一套 UI 风格（居中布局 + 状态驱动）。

按键：
- C 键（Key_Back）：退出
- D 键（Key_Return）：切换蓝牙模式（由 gamepad 入口拦截）
- A 键（Key_Left）：键位映射 QR 页
"""
import os
import sys
import time
import signal
import threading

# ===================== 阶段计时 =====================
T0 = time.monotonic()


def mark(name: str):
    ms = (time.monotonic() - T0) * 1000.0
    print(f"[joystick][+{ms:7.1f}ms] {name}", flush=True)


mark("python entry")

# ===================== PySide6 =====================
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QSocketNotifier
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QFrame,
)

mark("PySide6 import done")

# ===================== 主题 =====================
_LUWU_ROOT = os.environ.get("LUWU_ROOT", "/opt/luwu-os")
if _LUWU_ROOT not in sys.path:
    sys.path.insert(0, _LUWU_ROOT)

from libs.theme import (  # noqa: E402
    apply_app_palette, Asset as T_Asset, Color as T_Color,
    Spacing, qss as T_qss,
)
from libs.ui import AppFrame  # noqa: E402
from libs.ui.frame import _invisible_cursor  # noqa: E402
from libs.i18n import Translator as _Translator  # noqa: E402

mark("theme import done")

# ===================== 键位映射相关 =====================
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

# mapping_server 和 qr_page 统一从 gamepad 目录导入
# 与蓝牙页面共享同一个 mapping_server 模块实例，避免端口/全局状态冲突
_GAMEPAD_DIR = os.path.join(_LUWU_ROOT, "apps/gamepad")
if _GAMEPAD_DIR not in sys.path:
    sys.path.insert(0, _GAMEPAD_DIR)
import mapping_server  # noqa: E402
from qr_page import QRMappingPage  # noqa: E402

mark("mapping imports done")

# ===================== i18n =====================
_T = _Translator({
    "cn": {
        "title": "2.4G 遥控",
        "init": "正在初始化 2.4G 遥控...",
        "connected": "2.4G 已连接",
        "ready": "手柄就绪，正在控制机器狗",
        "disconnected": "2.4G 未连接，请插入接收器",
        "hint_exit": "退出",
        "hint_mapping": "键位映射",
        "hint_bt": "D 切换蓝牙",
        "key_mapping": "键位映射",
        "back": "返回",
    },
    "en": {
        "title": "2.4G Remote",
        "init": "Initializing 2.4G remote...",
        "connected": "2.4G Connected",
        "ready": "Gamepad ready, controlling robot",
        "disconnected": "2.4G Disconnected, insert receiver",
        "hint_exit": "Exit",
        "hint_mapping": "Key Map",
        "hint_bt": "D BT Mode",
        "key_mapping": "Key Mapping",
        "back": "Back",
    },
})

# ===================== 常量 =====================
AUTO_EXIT_SEC = 1800  # 30 分钟无操作自动退出
_LAUNCHER_ASSETS = os.path.dirname(T_Asset.bg_image)
DEMO_ICON = os.path.join(_LAUNCHER_ASSETS, "demo_gamepad.png")
_APP_BG_IMAGE = os.path.join(_LUWU_ROOT, "assets/images/app_bg.png")
KEYS_FIFO = "/tmp/luwu_keys.fifo"  # launcher 通过此 FIFO 转发物理按键

# ===================== XGO 单例 =====================
_xgo_instance = None
_xgo_device_type = None


def _ensure_xgo():
    """懒初始化 xgolib 单例，全局复用"""
    global _xgo_instance, _xgo_device_type
    if _xgo_instance is not None:
        return _xgo_instance, _xgo_device_type
    try:
        from xgolib import XGO
        print("[joystick] initializing xgolib (one-time)...", flush=True)
        _xgo_instance = XGO()
        fw = getattr(_xgo_instance, "version", "")
        if fw and fw[0] == "R":
            _xgo_device_type = "xgorider"
        elif fw and fw[0] == "L":
            _xgo_device_type = "xgolite"
        else:
            _xgo_device_type = "xgomini"
        print(f"[joystick] xgolib ready: {_xgo_device_type} (fw={fw})", flush=True)
    except ImportError:
        print("[joystick] xgolib not installed, debug mode", flush=True)
    except Exception as e:
        print(f"[joystick] xgolib init failed: {e}", flush=True)
    return _xgo_instance, _xgo_device_type


# ===================== 控制器线程 =====================
class ControllerThread(threading.Thread):
    """后台运行 JoystickController（2.4G 模式通过 /dev/input/js* 读取手柄）"""

    def __init__(self):
        super().__init__(daemon=True, name="joystick-gamepad-ctrl")
        self._controller = None
        self._device_name = ""

    @property
    def connected(self) -> bool:
        c = self._controller
        if c is None or not c._running:
            return False
        # JoystickController 通过 _js_reader.connected 判断连接状态
        if hasattr(c, '_js_reader') and c._js_reader is not None:
            return c._js_reader.connected
        return False

    @property
    def device_name(self) -> str:
        return self._device_name

    def run(self):
        mark("ControllerThread.run() enter")
        try:
            print("[joystick] ControllerThread -> importing gamepad_controller...", flush=True)
            gp_dir = os.path.join(os.environ.get("LUWU_ROOT", "/opt/luwu-os"), "libs/gamepad_config")
            if gp_dir not in sys.path:
                sys.path.insert(0, gp_dir)
            import gamepad_controller as gc
            gc.CONFIG_FILE = os.path.join(gp_dir, "mappings.json")
            print("[joystick] ControllerThread -> gamepad_controller imported", flush=True)

            # 导入 JoystickController（通过 /dev/input/js* 读取 2.4G 手柄）
            _gamepad_dir = os.path.join(os.environ.get("LUWU_ROOT", "/opt/luwu-os"), "apps/gamepad")
            if _gamepad_dir not in sys.path:
                sys.path.insert(0, _gamepad_dir)
            print("[joystick] ControllerThread -> importing JoystickController...", flush=True)
            from joystick_adapter import JoystickController
            print("[joystick] ControllerThread -> JoystickController imported", flush=True)

            print("[joystick] ControllerThread -> creating JoystickController(js_id=0)...", flush=True)
            self._controller = JoystickController(js_id=0)
            print("[joystick] ControllerThread -> JoystickController created", flush=True)

            # 注入全局 xgolib 单例
            xgo, dev_type = _ensure_xgo()
            if xgo is not None:
                self._controller.xgo = xgo
                self._controller.device_type = dev_type
                print(f"[joystick] ControllerThread -> xgolib ready: {dev_type}", flush=True)
            else:
                self._controller.xgo = False
                self._controller.device_type = "none"
                print("[joystick] ControllerThread -> xgolib unavailable, xgo=False", flush=True)

            # 注入 FIFO fd，让 ControllerThread 主循环直接检查按键（不依赖 Qt QSocketNotifier）
            self._controller._keys_fifo_fd = self._open_keys_fifo()

            self._device_name = "2.4G Joystick"
            print("[joystick] ControllerThread -> calling _controller.run()...", flush=True)
            mark("_controller.run() start")
            self._controller.run()  # 内部会处理 _load_mapping / _start_config_watcher / JS 轮询
            print("[joystick] ControllerThread -> _controller.run() returned", flush=True)
        except Exception as e:
            print(f"[joystick] controller error: {e}", flush=True)
            import traceback
            traceback.print_exc()

    @staticmethod
    def _open_keys_fifo():
        """打开 launcher 的按键转发 FIFO，非阻塞"""
        try:
            fd = os.open(KEYS_FIFO, os.O_RDONLY | os.O_NONBLOCK)
            print(f"[joystick] ControllerThread -> Keys FIFO fd={fd} opened", flush=True)
            return fd
        except Exception as e:
            print(f"[joystick] ControllerThread -> Keys FIFO open failed: {e}", flush=True)
            return -1

    def stop(self):
        print("[joystick] ControllerThread.stop() enter", flush=True)
        c = self._controller
        if not c:
            print("[joystick] ControllerThread.stop() -> no controller, return", flush=True)
            return
        try:
            print("[joystick] ControllerThread.stop() -> set _running=False", flush=True)
            c._running = False
            # 先停 joystick reader（关闭 fd 可立即解除 read_loop 阻塞）
            if hasattr(c, '_js_reader') and c._js_reader:
                print("[joystick] ControllerThread.stop() -> stop js_reader", flush=True)
                c._js_reader.stop()
                print("[joystick] ControllerThread.stop() -> js_reader stopped", flush=True)
            # _stop_movement() 内部 xgo.stop() 是串口阻塞调用，
            # 不在此处等待，交给 ControllerThread 后台线程的 run() 清理
            self._device_name = ""
            print("[joystick] ControllerThread.stop() -> done", flush=True)
        except Exception as e:
            print(f"[joystick] controller stop error: {e}", flush=True)


# ===================== UI =====================
class JoystickPage(AppFrame):
    """2.4G 遥控界面 — 与蓝牙页面相同的居中布局风格"""

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._first_paint_logged = False
        self._exiting = False

        # 隐藏光标（手柄 App 不需要鼠标光标）
        self._cursor_timer.stop()
        self._cursor_hidden = True
        self.setCursor(_invisible_cursor())

        self._ctrl_thread: ControllerThread | None = None

        # ---- 标题 ----
        self.setTitle(_T("title"))

        # ---- QR 映射页（覆盖层，初始隐藏）----
        self._qr_page = QRMappingPage(self)
        self._qr_page.go_back = self._hide_qr_page
        self._qr_page.hide()

        # ---- 背景 ----
        _pix = QPixmap(_APP_BG_IMAGE)
        if not _pix.isNull():
            self._bg_pix = _pix
            self.update()

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
            tl=(_T("hint_mapping"), T_Asset.icon_left),
            bl=(_T("hint_exit"), T_Asset.icon_back),
        )

        QTimer.singleShot(AUTO_EXIT_SEC * 1000, self.close)
        QTimer.singleShot(200, self._start_controller)

        # ---- 监听 launcher 转发的物理按键（C/A/D 等）----
        self._keys_fd = -1
        self._keys_notifier = None
        self._setup_keys_fifo()

    # ---- launcher FIFO 按键转发 ----
    def _setup_keys_fifo(self):
        try:
            self._keys_fd = os.open(KEYS_FIFO, os.O_RDONLY | os.O_NONBLOCK)
            self._keys_notifier = QSocketNotifier(
                self._keys_fd, QSocketNotifier.Type.Read, self
            )
            self._keys_notifier.activated.connect(self._on_key_fifo)
            print("[joystick] Keys FIFO opened", flush=True)
        except Exception as e:
            print(f"[joystick] Keys FIFO error: {e}", flush=True)

    def _on_key_fifo(self, fd: int):
        try:
            data = os.read(fd, 32)
            if not data:
                return
            for line in data.decode().strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                qt_key = int(line)
                print(f"[joystick] FIFO recv Qt key={qt_key} (0x{qt_key:x})", flush=True)
                ev = QKeyEvent(QKeyEvent.Type.KeyPress, qt_key, Qt.KeyboardModifier.NoModifier)
                QApplication.postEvent(self, ev)
        except Exception as e:
            print(f"[joystick] key fifo read error: {e}", flush=True)

    # ---- 布局 ----
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        top = max(28, h * 14 // 100)
        bottom = max(20, h * 8 // 100)
        self._center.setGeometry(0, top, w, h - top - bottom)

        if self._qr_page:
            self._qr_page.setGeometry(0, 0, w, h)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self._first_paint_logged:
            self._first_paint_logged = True
            mark("first paintEvent")

    # ---- 控制器启停 ----
    def _start_controller(self):
        """启动手柄控制器线程"""
        mark("_start_controller enter")
        # 启动键位映射 Web 服务器
        try:
            print("[joystick] _start_controller -> starting mapping_server", flush=True)
            mapping_server.set_mode("joystick")
            mapping_server.start_server()
            print("[joystick] _start_controller -> mapping_server started", flush=True)
        except Exception as e:
            print(f"[joystick] mapping server start failed: {e}", flush=True)

        if self._ctrl_thread and self._ctrl_thread.is_alive():
            print("[joystick] _start_controller -> already running, skip", flush=True)
            return
        print("[joystick] _start_controller -> creating ControllerThread", flush=True)
        self._ctrl_thread = ControllerThread()
        print("[joystick] _start_controller -> starting ControllerThread", flush=True)
        self._ctrl_thread.start()
        print("[joystick] _start_controller -> ControllerThread started", flush=True)
        # 启动状态轮询
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_status)
        self._poll_timer.start(1000)
        print("[joystick] _start_controller -> poll timer started", flush=True)
        mark("_start_controller done")

    def _stop_controller(self):
        """停止手柄控制器（不在此处停止 mapping_server，统一由 closeEvent 处理）"""
        print("[joystick] _stop_controller() enter", flush=True)
        if self._ctrl_thread:
            print("[joystick] _stop_controller() -> calling ctrl_thread.stop()", flush=True)
            self._ctrl_thread.stop()
            print("[joystick] _stop_controller() -> ctrl_thread.stop() returned", flush=True)
        print("[joystick] _stop_controller() -> done", flush=True)

    def _poll_status(self):
        """每秒轮询控制器状态并更新 UI"""
        if not self._ctrl_thread or not self._ctrl_thread.is_alive():
            print("[joystick] _poll_status -> ctrl_thread not alive, skipping", flush=True)
            return
        if self._ctrl_thread.connected:
            name = self._ctrl_thread.device_name
            self.device_label.setText(name)
            self.status_label.setText(_T("connected"))
            self.status_label.setStyleSheet(T_qss.chip("success"))
            self.sub_label.setText(_T("ready"))
        else:
            self.device_label.setText("")
            self.status_label.setText(_T("disconnected"))
            self.status_label.setStyleSheet(T_qss.chip("danger"))
            self.sub_label.setText("")
        # 每 5 次打印心跳确认 UI 线程活着
        if not hasattr(self, '_poll_count'):
            self._poll_count = 0
        self._poll_count += 1
        if self._poll_count % 5 == 0:
            print(f"[joystick] _poll_status heartbeat #{self._poll_count}, connected={self._ctrl_thread.connected}", flush=True)

    # ---- QR 映射页 ----
    def _show_qr_page(self):
        print("[joystick] showing QR mapping page", flush=True)
        if not mapping_server.is_running():
            try:
                mapping_server.set_mode("joystick")
                mapping_server.start_server()
            except Exception as e:
                print(f"[joystick] mapping server start failed: {e}", flush=True)
        try:
            self._qr_page._generate()
        except Exception as e:
            print(f"[joystick] QR generate failed: {e}", flush=True)
        self._qr_page.show()
        self._qr_page.raise_()
        self._qr_page.setFocus()
        self._center.hide()
        self.icon_label.hide()
        self.accent_line.hide()
        self.device_label.hide()
        self.status_label.hide()
        self.sub_label.hide()
        for c in self._corners.values():
            c.hide()

    def _hide_qr_page(self):
        print("[joystick] hiding QR mapping page", flush=True)
        self._qr_page.hide()
        self._center.show()
        self.icon_label.show()
        self.accent_line.show()
        self.device_label.show()
        self.status_label.show()
        self.sub_label.show()
        for c in self._corners.values():
            c.show()
        self.setFocus()

    # ---- 按键 ----
    def keyPressEvent(self, ev: QKeyEvent):
        key = ev.key()
        # QR 页面可见时优先处理返回
        if self._qr_page.isVisible():
            if key == Qt.Key.Key_Back:
                print("[joystick] C -> back from QR", flush=True)
                self._hide_qr_page()
                return
            self._qr_page.keyPressEvent(ev)
            return

        if key == Qt.Key.Key_Back:
            if self._exiting:
                print("[joystick] C -> already exiting, skip", flush=True)
                return
            self._exiting = True
            mark("C key -> exit")
            print("[joystick] C -> exit (hard fallback 0.5s)", flush=True)

            # ★ 硬兜底：不依赖 Qt event loop，0.5s 后必杀进程
            threading.Timer(0.5, lambda: os._exit(0)).start()

            # 优雅路径：尝试正常清理（如果 Qt 还能运转）
            try:
                self._stop_controller()
            except Exception as e:
                print(f"[joystick] _stop_controller error: {e}", flush=True)
            try:
                mapping_server.stop_server()
            except Exception:
                pass
            QApplication.instance().quit()
        elif key == Qt.Key.Key_Left:
            # A 键 → 打开键位映射
            print("[joystick] A -> key mapping", flush=True)
            self._show_qr_page()

    # ---- 退出清理 ----
    def closeEvent(self, ev):
        mark("closeEvent enter")
        print("[joystick] closeEvent -> _stop_controller", flush=True)
        self._stop_controller()
        print("[joystick] closeEvent -> mapping_server.stop_server", flush=True)
        try:
            mapping_server.stop_server()
        except Exception:
            pass
        print("[joystick] closeEvent -> mapping_server done", flush=True)
        print("[joystick] closeEvent -> super().closeEvent", flush=True)
        super().closeEvent(ev)
        print("[joystick] closeEvent -> done", flush=True)


# ===================== 入口 =====================
def main():
    signal.signal(signal.SIGINT, lambda *_: QApplication.instance().quit())
    signal.signal(signal.SIGTERM, lambda *_: QApplication.instance().quit())

    app = QApplication(sys.argv)
    apply_app_palette(app)
    mark("QApplication created")

    w = JoystickPage()
    mark("widget constructed")

    w.showFullScreen()
    mark("showFullScreen returned")

    rc = app.exec()
    print(f"[joystick] exit rc={rc}", flush=True)
    sys.exit(rc)


if __name__ == "__main__":
    main()

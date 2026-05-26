#!/usr/bin/env python3
"""
合并手柄控制 — Luwu OS 统一入口

自动检测输入源：
  - /dev/input/js0 存在 → 2.4G Joystick 模式（默认优先）
  - 否则 → 蓝牙扫描配对模式

按键：
  - C 键（Key_Back）：退出
  - A 键（Key_Left）：键位映射 QR 页（子页面处理）
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
    print(f"[gamepad][+{ms:7.1f}ms] {name}", flush=True)


mark("python entry")

# ===================== 自动检测输入源 =====================
JS0_PATH = "/dev/input/js0"


def _is_usb_joystick(js_dev: str = "js0") -> bool:
    """判断 joystick 设备是否来自 USB（2.4G 接收器）。

    蓝牙 HID 设备的 sysfs uniq 字段包含蓝牙 MAC 地址（XX:XX:XX:XX:XX:XX），
    而 USB 设备的 uniq 字段为空。以此区分 2.4G USB 接收器和蓝牙手柄。
    """
    try:
        uniq_path = f"/sys/class/input/{js_dev}/device/uniq"
        with open(uniq_path) as f:
            uniq = f.read().strip()
        # 非空且含冒号 → 蓝牙设备，不是 USB
        if uniq and ":" in uniq:
            print(f"[gamepad] {js_dev} is bluetooth (uniq={uniq}), skip", flush=True)
            return False
        return True
    except OSError:
        return True  # 读取失败时保守认为是 USB


def detect_mode() -> str:
    """检测当前可用的输入模式"""
    if os.path.exists(JS0_PATH) and _is_usb_joystick():
        return "joystick"
    return "bluetooth"


def is_joystick_available() -> bool:
    return os.path.exists(JS0_PATH) and _is_usb_joystick()


_CURRENT_MODE = detect_mode()
mark(f"auto-detect: {_CURRENT_MODE}")

# ===================== PySide6 =====================
from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QStackedWidget

mark("PySide6 import done")

# ---- luwu-os 主题层 ----
_LUWU_ROOT = os.environ.get("LUWU_ROOT", "/opt/luwu-os")
if _LUWU_ROOT not in sys.path:
    sys.path.insert(0, _LUWU_ROOT)
from libs.theme import apply_app_palette  # noqa: E402
from libs.i18n import Translator as _Translator  # noqa: E402

mark("theme import done")

# ===================== i18n =====================
_T = _Translator({
    "cn": {
        "title_joystick": "手柄控制",
        "title_bluetooth": "蓝牙遥控",
    },
    "en": {
        "title_joystick": "Gamepad",
        "title_bluetooth": "BT Gamepad",
    },
})

# ===================== 导入两种页面 =====================
# 延迟导入，避免蓝牙初始化副作用影响 joystick 模式

_joystick_page_cls = None
_bt_page_cls = None


def _import_joystick_page():
    """延迟导入 JoystickPage（纯 UI，无副作用）"""
    global _joystick_page_cls
    if _joystick_page_cls is not None:
        return _joystick_page_cls
    # 从现有 joystick app 导入页面类
    _js_dir = os.path.join(os.environ.get("LUWU_ROOT", "/opt/luwu-os"), "apps/joystick")
    if _js_dir not in sys.path:
        sys.path.insert(0, _js_dir)
    # 注意：导入 joystick/main.py 会执行其模块级代码但不会启动 QApplication
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "joystick_main", os.path.join(_js_dir, "main.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _joystick_page_cls = mod.JoystickPage
    return _joystick_page_cls


def _import_bt_page():
    """延迟导入 BTGamepadPage"""
    global _bt_page_cls
    if _bt_page_cls is not None:
        return _bt_page_cls
    _bt_dir = os.path.join(os.environ.get("LUWU_ROOT", "/opt/luwu-os"), "apps/bluetooth_gamepad")
    if _bt_dir not in sys.path:
        sys.path.insert(0, _bt_dir)
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "bt_main", os.path.join(_bt_dir, "main.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _bt_page_cls = mod.BTGamepadPage
    return _bt_page_cls


# ===================== 主窗口 =====================
class GamepadApp(QStackedWidget):
    """统一手柄控制应用，使用 QStackedWidget 管理两种页面。

    通过 eventFilter 拦截子页面的 C 按键，确保退出操作由 GamepadApp 统一处理。
    """

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._exiting = False
        self._mode = _CURRENT_MODE

        # 创建初始页面
        mark(f"creating {self._mode} page...")
        self._joystick_page = None
        self._bt_page = None

        if self._mode == "joystick":
            self._activate_joystick()
        else:
            self._activate_bluetooth()

        # 30 分钟无操作自动退出
        QTimer.singleShot(1800 * 1000, self.close)

    # ── eventFilter：拦截子页面 C 键 ────────────────────────

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Back:
                if not self._exiting:
                    self._exiting = True
                    print("[gamepad] C -> exit", flush=True)
                    self._do_close()
                return True  # 消费事件，子页面不处理
            # D 键不再切换模式，自动检测即可（插2.4G=joystick，否则=蓝牙）
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                pass  # 忽略，蓝牙页面自行处理重新扫描
        return super().eventFilter(watched, event)

    # ── 页面切换 ──────────────────────────────────────────────

    def _activate_joystick(self):
        """激活 joystick 页面"""
        if self._bt_page:
            self._bt_page.close()
            self._bt_page.removeEventFilter(self)
            self.removeWidget(self._bt_page)
            self._bt_page = None

        if not self._joystick_page:
            _import_joystick_page()
            self._joystick_page = _joystick_page_cls()
            self._joystick_page.installEventFilter(self)
            self.addWidget(self._joystick_page)

        self.setCurrentWidget(self._joystick_page)
        self._mode = "joystick"
        self._joystick_page.setFocus()
        mark("joystick page active")

    def _activate_bluetooth(self):
        """激活蓝牙页面"""
        if self._joystick_page:
            self._joystick_page.close()
            self._joystick_page.removeEventFilter(self)
            self.removeWidget(self._joystick_page)
            self._joystick_page = None

        if not self._bt_page:
            _import_bt_page()
            self._bt_page = _bt_page_cls()
            self._bt_page.installEventFilter(self)
            self.addWidget(self._bt_page)

        self.setCurrentWidget(self._bt_page)
        self._mode = "bluetooth"
        self._bt_page.setFocus()
        mark("bluetooth page active")

    def _do_close(self):
        """安全退出（加硬兜底，不依赖 Qt event loop）"""
        mark("_do_close enter")
        print("[gamepad] C -> exit, doing close+quit", flush=True)

        # ★ 硬兜底：threading.Timer 不依赖 Qt event loop，0.5s 后必杀
        threading.Timer(0.5, lambda: os._exit(0)).start()

        # 优雅路径：尝试正常清理
        print("[gamepad] _do_close -> calling self.close()", flush=True)
        self.close()
        print("[gamepad] _do_close -> self.close() returned", flush=True)
        print("[gamepad] _do_close -> calling quit()", flush=True)
        QApplication.instance().quit()
        print("[gamepad] _do_close -> quit() returned", flush=True)

    # ── 清理 ──────────────────────────────────────────────────

    def closeEvent(self, ev):
        mark("GamepadApp.closeEvent enter")
        if self._joystick_page:
            print("[gamepad] closeEvent -> closing joystick page", flush=True)
            self._joystick_page.removeEventFilter(self)
            self._joystick_page.close()
            print("[gamepad] closeEvent -> joystick page closed", flush=True)
        if self._bt_page:
            print("[gamepad] closeEvent -> closing bt page", flush=True)
            self._bt_page.removeEventFilter(self)
            self._bt_page.close()
            print("[gamepad] closeEvent -> bt page closed", flush=True)
        print("[gamepad] closeEvent -> super().closeEvent", flush=True)
        super().closeEvent(ev)
        print("[gamepad] closeEvent -> done", flush=True)


# ===================== 入口 =====================
def main():
    signal.signal(signal.SIGINT, lambda *_: QApplication.instance().quit())
    signal.signal(signal.SIGTERM, lambda *_: QApplication.instance().quit())

    app = QApplication(sys.argv)
    apply_app_palette(app)
    mark("QApplication created")

    w = GamepadApp()
    mark("widget constructed")

    w.showFullScreen()
    mark("showFullScreen returned")

    rc = app.exec()
    print(f"[gamepad] exit rc={rc}", flush=True)
    sys.exit(rc)


if __name__ == "__main__":
    main()

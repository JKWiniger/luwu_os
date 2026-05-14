#!/usr/bin/env python3
"""
PySide6 手柄控制 (Joystick Control) — 由 Luwu OS launcher 启动。
读取 /dev/input/js* 手柄设备，控制 XGO 机器狗运动。
C 键（左下物理键 → KEY_BACK）退出。
"""
import os
import sys
import time
import struct
import signal
import threading

# ===================== 阶段计时 =====================
T0 = time.monotonic()
_stages = []


def mark(name: str):
    ms = (time.monotonic() - T0) * 1000.0
    _stages.append((name, ms))
    print(f"[joystick][+{ms:7.1f}ms] {name}", flush=True)


mark("python entry")

# ===================== 重载导入 =====================
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QKeyEvent, QColor, QPalette
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QGridLayout, QProgressBar, QFrame,
)

mark("PySide6 import done")

# ===================== 狗库 =====================
sys.path.insert(0, "/home/pi/lib")
from xgolib import XGO

mark("xgolib import done")

# ===================== 常量 =====================
AUTO_EXIT_SEC = 600  # 10 分钟无操作自动退出


# ===================== 手柄读取类 =====================
class JoystickReader:
    """读取 Linux /dev/input/js* 手柄设备。"""

    # 按钮映射
    BUTTON_NAMES = {
        0x0100: "A",
        0x0101: "B",
        0x0102: "X",
        0x0103: "Y",
        0x0104: "L1",
        0x0105: "R1",
        0x0106: "SELECT",
        0x0107: "START",
        0x0108: "MODE",
        0x0109: "BTN_RK1",
        0x010A: "BTN_RK2",
    }

    # 轴映射
    AXIS_NAMES = {
        0x0200: "RK1_LEFT_RIGHT",
        0x0201: "RK1_UP_DOWN",
        0x0202: "L2",
        0x0203: "RK2_LEFT_RIGHT",
        0x0204: "RK2_UP_DOWN",
        0x0205: "R2",
        0x0206: "WSAD_LEFT_RIGHT",
        0x0207: "WSAD_UP_DOWN",
    }

    def __init__(self, js_id=0):
        self._js_id = js_id
        self._jsdev = None
        self._connected = False
        self._running = False
        self._thread = None
        self._last_reconnect_attempt = 0  # 上次重连尝试时间

        # 状态缓存
        self.button_states = {name: 0 for name in self.BUTTON_NAMES.values()}
        self.axis_states = {name: 0.0 for name in self.AXIS_NAMES.values()}

        self._try_open()

    def _try_open(self):
        """尝试打开手柄设备。"""
        js_path = f"/dev/input/js{self._js_id}"
        try:
            self._jsdev = open(js_path, "rb")
            self._connected = True
            print(f"[joystick] 手柄已连接: {js_path}", flush=True)
        except Exception:
            self._connected = False
            print(f"[joystick] 未找到手柄: {js_path}", flush=True)

    @property
    def connected(self):
        return self._connected

    def start(self):
        """启动后台读取线程。"""
        if not self._connected:
            return
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止读取。"""
        self._running = False
        if self._jsdev:
            try:
                self._jsdev.close()
            except Exception:
                pass
            self._jsdev = None
        self._connected = False

    def _read_loop(self):
        """后台持续读取手柄事件。"""
        while self._running and self._connected:
            try:
                evbuf = self._jsdev.read(8)
                if evbuf:
                    t, value, etype, number = struct.unpack("IhBB", evbuf)
                    func = (etype << 8) | number

                    if func in self.BUTTON_NAMES:
                        name = self.BUTTON_NAMES[func]
                        self.button_states[name] = value
                    elif func in self.AXIS_NAMES:
                        name = self.AXIS_NAMES[func]
                        self.axis_states[name] = value / 32767.0
            except BlockingIOError:
                time.sleep(0.01)
            except Exception as e:
                print(f"[joystick] 读取错误: {e}", flush=True)
                self._connected = False
                break

    def try_reconnect(self):
        """尝试重连手柄（每 2 秒最多一次）。"""
        now = time.monotonic()
        if now - self._last_reconnect_attempt < 2.0:
            return
        self._last_reconnect_attempt = now
        if not self._connected:
            self._try_open()
            if self._connected:
                self.start()


# ===================== 机器狗控制 =====================
class DogController:
    """将手柄输入翻译为机器狗控制指令。"""

    STEP_SCALE_X = 0.25
    STEP_SCALE_Y = 0.2
    STEP_SCALE_Z = 0.7

    def __init__(self):
        self._dog = None
        self._step_control = 70
        self._pace_freq = 2
        self._height = 105
        self._play_ball = 0
        self._crossing_state = False
        self._init_dog()

    def _init_dog(self):
        try:
            self._dog = XGO()
            print("[joystick] XGO 机器狗初始化成功", flush=True)
        except Exception as e:
            self._dog = None
            print(f"[joystick] XGO 初始化失败: {e}", flush=True)

    @property
    def dog_available(self):
        return self._dog is not None

    def _my_map(self, x, in_min, in_max, out_min, out_max):
        return (out_max - out_min) * (x - in_min) / (in_max - in_min) + out_min

    def reset(self):
        if self._dog:
            try:
                self._dog.reset()
            except Exception:
                pass
        self._step_control = 70
        self._pace_freq = 2
        self._height = 105
        self._crossing_state = False

    def process_event(self, name, value):
        """处理单个手柄事件。"""
        if not self._dog:
            return

        try:
            if name == "RK1_LEFT_RIGHT":
                v = -value
                if self._crossing_state:
                    return
                fvalue = int(self._step_control * self.STEP_SCALE_Y * v)
                self._dog.move("y", fvalue)

            elif name == "RK1_UP_DOWN":
                v = -value
                if self._crossing_state:
                    return
                fvalue = int(self._step_control * self.STEP_SCALE_X * v)
                self._dog.move("x", fvalue)

            elif name == "RK2_UP_DOWN":
                v = -value
                if self._crossing_state:
                    return
                if v == 0:
                    self._dog.turn(0)
                elif abs(v) > 0.9:
                    fvalue = int(self._my_map(self._step_control, 0, 100, 20, self.STEP_SCALE_Z * 100)) * (1 if v > 0 else -1)
                    self._dog.turn(fvalue)

            elif name == "RK2_LEFT_RIGHT":
                v = value
                if self._crossing_state:
                    return
                fvalue = int(v * 15)
                self._dog.attitude("p", fvalue)

            elif name == "A":
                if value == 1 and not self._crossing_state:
                    self._height = max(75, self._height - 10)
                    self._dog.translation("z", self._height)

            elif name == "B":
                if value == 1:
                    self._dog.attitude("y", -35)
                else:
                    self._dog.attitude("r", 0)
                    self._dog.attitude("y", 0)

            elif name == "X":
                if value == 1:
                    self._dog.attitude("y", 35)
                else:
                    self._dog.attitude("r", 0)
                    self._dog.attitude("y", 0)

            elif name == "Y":
                if value == 1 and not self._crossing_state:
                    self._height = min(115, self._height + 10)
                    self._dog.translation("z", self._height)

            elif name == "L1":
                if value == 1 and not self._crossing_state:
                    self._dog.action(10)

            elif name == "R1":
                if value == 1 and not self._crossing_state:
                    self._dog.action(11)

            elif name == "SELECT":
                if value == 1:
                    if not self._crossing_state:
                        self._crossing_state = True
                        self._dog.gait_type("high_walk")
                        time.sleep(0.01)
                        self._dog.pace("slow")
                        time.sleep(0.01)
                        self._dog.translation("z", 95)
                        time.sleep(0.01)
                        self._dog.forward(25)
                    else:
                        self.reset()

            elif name == "START":
                if value == 1:
                    self.reset()

            elif name == "BTN_RK1":
                if value == 1:
                    self._step_control += 30
                    if self._step_control > 100:
                        self._step_control = 40

            elif name == "BTN_RK2":
                if value == 1:
                    self._pace_freq += 1
                    if self._pace_freq > 3:
                        self._pace_freq = 1
                    pace_map = {1: "slow", 2: "normal", 3: "high"}
                    self._dog.pace(pace_map.get(self._pace_freq, "normal"))

            elif name == "L2":
                v = (value + 1) / 2
                if v > 0.95:
                    self._dog.action(16)

            elif name == "R2":
                v = (value + 1) / 2
                if v > 0.95:
                    self._dog.action(11)

            elif name == "WSAD_LEFT_RIGHT":
                v = -value
                if self._crossing_state:
                    return
                fvalue = v * self._step_control * self.STEP_SCALE_Y
                self._dog.move("y", fvalue)

            elif name == "WSAD_UP_DOWN":
                v = -value
                if self._crossing_state:
                    return
                fvalue = int(v * self._step_control * self.STEP_SCALE_X)
                self._dog.move("x", fvalue)

        except Exception as e:
            print(f"[joystick] 控制错误 ({name}={value}): {e}", flush=True)

    @property
    def step_control(self):
        return self._step_control

    @property
    def pace_freq(self):
        return self._pace_freq

    @property
    def height(self):
        return self._height


# ===================== PySide6 页面 =====================
class JoystickPage(QWidget):
    """手柄控制 LCD 界面。"""

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #0f1530;")
        self._first_paint_logged = False

        # ---- 手柄读取器 ----
        self._js = JoystickReader(js_id=0)

        # ---- 机器狗控制器 ----
        self._controller = DogController()

        # ---- 标题 ----
        self.title = QLabel("🎮 手柄控制")
        f1 = QFont()
        f1.setPointSize(18)
        f1.setBold(True)
        self.title.setFont(f1)
        self.title.setStyleSheet("color: white;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ---- 连接状态 ----
        self.status_label = QLabel("手柄未连接")
        self.status_label.setStyleSheet("color: #ff6b6b; font-size: 14px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.dog_label = QLabel("机器狗: --")
        self.dog_label.setStyleSheet("color: #8892c9; font-size: 12px;")
        self.dog_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ---- 分隔线 ----
        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.Shape.HLine)
        self.separator.setStyleSheet("color: #2a3050;")

        # ---- 摇杆状态显示 ----
        self.axis_grid_title = QLabel("— 摇杆轴状态 —")
        self.axis_grid_title.setStyleSheet("color: #5c6a9c; font-size: 11px;")
        self.axis_grid_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.axis_labels = {}
        axis_grid = QGridLayout()
        axis_grid.setSpacing(4)
        axis_names_display = [
            ("RK1 ←→", "RK1_LEFT_RIGHT"),
            ("RK1 ↑↓", "RK1_UP_DOWN"),
            ("RK2 ←→", "RK2_LEFT_RIGHT"),
            ("RK2 ↑↓", "RK2_UP_DOWN"),
            ("L2", "L2"),
            ("R2", "R2"),
            ("WSAD ←→", "WSAD_LEFT_RIGHT"),
            ("WSAD ↑↓", "WSAD_UP_DOWN"),
        ]
        for i, (display_name, key) in enumerate(axis_names_display):
            name_lbl = QLabel(display_name)
            name_lbl.setStyleSheet("color: #8892c9; font-size: 10px;")
            bar = QProgressBar()
            bar.setRange(-100, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(10)
            bar.setStyleSheet("""
                QProgressBar {
                    background-color: #1a1f3a; border: none; border-radius: 3px;
                }
                QProgressBar::chunk {
                    background-color: #18df6b; border-radius: 3px;
                }
            """)
            self.axis_labels[key] = bar
            row = i // 2
            col = (i % 2) * 2
            axis_grid.addWidget(name_lbl, row, col)
            axis_grid.addWidget(bar, row, col + 1)

        # ---- 按钮状态显示 ----
        self.btn_grid_title = QLabel("— 按钮状态 —")
        self.btn_grid_title.setStyleSheet("color: #5c6a9c; font-size: 11px;")
        self.btn_grid_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_labels = {}
        btn_grid = QGridLayout()
        btn_grid.setSpacing(4)
        btn_names = ["A", "B", "X", "Y", "L1", "R1", "SELECT", "START", "MODE", "RK1", "RK2"]
        for i, name in enumerate(btn_names):
            lbl = QLabel(name)
            lbl.setFixedSize(36, 20)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                "color: #5c6a9c; background-color: #1a1f3a; border-radius: 4px; font-size: 10px;"
            )
            self.btn_labels[name] = lbl
            row = i // 6
            col = i % 6
            btn_grid.addWidget(lbl, row, col)

        # ---- 参数显示 ----
        self.param_label = QLabel("步幅: 70  步频: 2  高度: 105")
        self.param_label.setStyleSheet("color: #18df6b; font-size: 12px;")
        self.param_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ---- 操作提示 ----
        hint_style = "color: #5c6a9c; font-size: 10px; background: transparent;"
        self.hint_bl = QLabel("C: 退出", self)
        self.hint_bl.setStyleSheet(hint_style)
        self.hint_br = QLabel("SELECT: 复位", self)
        self.hint_br.setStyleSheet(hint_style)
        self.hint_br.setAlignment(Qt.AlignmentFlag.AlignRight)

        # ---- 布局 ----
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(6)
        main_layout.addWidget(self.title)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.dog_label)
        main_layout.addWidget(self.separator)
        main_layout.addWidget(self.axis_grid_title)
        main_layout.addLayout(axis_grid)
        main_layout.addWidget(self.btn_grid_title)
        main_layout.addLayout(btn_grid)
        main_layout.addWidget(self.param_label)

        # ---- 定时刷新 ----
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_ui)
        self._refresh_timer.start(80)  # ~12fps

        # ---- 手柄轮询定时器（同时处理事件和重连） ----
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_joystick)
        self._poll_timer.start(20)  # ~50Hz 轮询

        # ---- 自动退出兜底 ----
        QTimer.singleShot(AUTO_EXIT_SEC * 1000, self.close)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # ---- 启动手柄读取 ----
        self._js.start()

    def _poll_joystick(self):
        """轮询手柄状态并控制机器狗。"""
        if not self._js.connected:
            self._js.try_reconnect()
            return

        # 处理按钮事件（只处理变化）
        for name, value in self._js.button_states.items():
            if value != 0:  # 有按下或持续按住
                self._controller.process_event(name, value)

        # 处理轴事件
        for name, value in self._js.axis_states.items():
            self._controller.process_event(name, value)

    def _refresh_ui(self):
        """刷新界面显示。"""
        connected = self._js.connected
        if connected:
            self.status_label.setText("🟢 手柄已连接")
            self.status_label.setStyleSheet("color: #18df6b; font-size: 14px;")
        else:
            self.status_label.setText("🔴 手柄未连接")
            self.status_label.setStyleSheet("color: #ff6b6b; font-size: 14px;")

        if self._controller.dog_available:
            self.dog_label.setText("🟢 机器狗已就绪")
        else:
            self.dog_label.setText("🔴 机器狗未连接")

        # 更新轴进度条
        for name, bar in self.axis_labels.items():
            val = self._js.axis_states.get(name, 0)
            bar.setValue(int(val * 100))

        # 更新按钮高亮
        btn_key_map = {
            "A": "A", "B": "B", "X": "X", "Y": "Y",
            "L1": "L1", "R1": "R1",
            "SELECT": "SELECT", "START": "START", "MODE": "MODE",
            "RK1": "BTN_RK1", "RK2": "BTN_RK2",
        }
        for display_name, internal_name in btn_key_map.items():
            if display_name in self.btn_labels:
                lbl = self.btn_labels[display_name]
                pressed = self._js.button_states.get(internal_name, 0)
                if pressed:
                    lbl.setStyleSheet(
                        "color: #fff; background-color: #18df6b; border-radius: 4px; font-size: 10px;"
                    )
                else:
                    lbl.setStyleSheet(
                        "color: #5c6a9c; background-color: #1a1f3a; border-radius: 4px; font-size: 10px;"
                    )

        # 更新参数
        pace_names = {1: "慢", 2: "中", 3: "快"}
        self.param_label.setText(
            f"步幅: {self._controller.step_control}  "
            f"步频: {pace_names.get(self._controller.pace_freq, '中')}  "
            f"高度: {self._controller.height}"
        )

    # ---- 布局事件 ----
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        w, h = self.width(), self.height()
        pad = 16
        self.hint_bl.adjustSize()
        self.hint_bl.move(pad, h - self.hint_bl.height() - pad)
        self.hint_br.adjustSize()
        self.hint_br.move(w - self.hint_br.width() - pad, h - self.hint_br.height() - pad)

    # ---- 首帧日志 ----
    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self._first_paint_logged:
            self._first_paint_logged = True
            mark("first paintEvent")
            summary = self._stage_summary()
            print("[joystick] boot breakdown:\n" + summary, flush=True)

    def _stage_summary(self) -> str:
        lines = []
        prev = 0.0
        for name, ms in _stages:
            lines.append(f"{name}: {ms:.0f}ms (+{ms - prev:.0f})")
            prev = ms
        return " | ".join(lines)

    # ---- 按键 ----
    def keyPressEvent(self, ev: QKeyEvent):
        if ev.key() == Qt.Key.Key_Back:
            # 左下 C 键 → 退出
            print("[joystick] KEY_BACK -> exit", flush=True)
            self.close()

    def closeEvent(self, ev):
        print("[joystick] closing", flush=True)
        self._poll_timer.stop()
        self._refresh_timer.stop()
        self._js.stop()
        self._controller.reset()
        super().closeEvent(ev)


# ===================== 入口 =====================
def main():
    signal.signal(signal.SIGINT, lambda *_: QApplication.instance().quit())
    signal.signal(signal.SIGTERM, lambda *_: QApplication.instance().quit())

    app = QApplication(sys.argv)
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

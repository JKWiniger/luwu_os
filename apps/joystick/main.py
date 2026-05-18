#!/usr/bin/env python3
"""
PySide6 手柄控制 (Joystick Control) — 由 Luwu OS launcher 启动。
读取 /dev/input/js* 手柄设备，控制 XGO 机器狗运动。
C 键（左下物理键 → KEY_BACK）退出。
"""
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

# ===================== PySide6 =====================
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QFont, QKeyEvent, QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFrame,
)

mark("PySide6 import done")

# ===================== 狗库 =====================
sys.path.insert(0, "/home/pi/lib")
from xgolib import XGO

mark("xgolib import done")

# ===================== 主题 =====================
if "/home/pi/luwu-os" not in sys.path:
    sys.path.insert(0, "/home/pi/luwu-os")

from libs.theme import apply_app_palette, Asset, Color as T, ColorRGB
from libs.theme import qss as T_qss
from libs.theme.tokens import Font, Spacing, Radius
from libs.ui import AppFrame

mark("theme import done")

# ===================== i18n =====================
try:
    from libs.i18n import Translator as _Translator
    _T = _Translator({
        "cn": {
            "title": "手柄控制",
            "joystick_connected": "手柄 已连接",
            "joystick_disconnected": "手柄 未连接",
            "dog_ready": "机器狗 就绪",
            "dog_offline": "机器狗 离线",
            "step": "步幅",
            "pace": "步频",
            "height": "高度",
            "pace_slow": "慢",
            "pace_med": "中",
            "pace_fast": "快",
            "hint_exit": "退出",
            "hint_action": "START:复位  SELECT:跨障",
        },
        "en": {
            "title": "Gamepad",
            "joystick_connected": "Pad: Connected",
            "joystick_disconnected": "Pad: Disconnected",
            "dog_ready": "Dog: Ready",
            "dog_offline": "Dog: Offline",
            "step": "Step",
            "pace": "Pace",
            "height": "Height",
            "pace_slow": "Slow",
            "pace_med": "Med",
            "pace_fast": "Fast",
            "hint_exit": "Exit",
            "hint_action": "START:Reset  SELECT:Climb",
        },
    })
except Exception:
    _T = lambda k, *a: k

# ===================== 常量 =====================
AUTO_EXIT_SEC = 600  # 10 分钟无操作自动退出


# ===================== 手柄读取类 =====================
class JoystickReader:
    """读取 Linux /dev/input/js* 手柄设备。"""

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
        self._last_reconnect_attempt = 0

        self.button_states = {name: 0 for name in self.BUTTON_NAMES.values()}
        self.axis_states = {name: 0.0 for name in self.AXIS_NAMES.values()}

        self._try_open()

    def _try_open(self):
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
        if not self._connected:
            return
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._jsdev:
            try:
                self._jsdev.close()
            except Exception:
                pass
            self._jsdev = None
        self._connected = False

    def _read_loop(self):
        while self._running and self._connected:
            try:
                evbuf = self._jsdev.read(8)
                if evbuf:
                    t, value, etype, number = struct.unpack("IhBB", evbuf)
                    func = (etype << 8) | number
                    if func in self.BUTTON_NAMES:
                        self.button_states[self.BUTTON_NAMES[func]] = value
                    elif func in self.AXIS_NAMES:
                        self.axis_states[self.AXIS_NAMES[func]] = value / 32767.0
            except BlockingIOError:
                time.sleep(0.01)
            except Exception as e:
                print(f"[joystick] 读取错误: {e}", flush=True)
                self._connected = False
                break

    def try_reconnect(self):
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
        self._play_ball = 0
        if self._dog:
            try:
                self._dog.reset()
            except Exception:
                pass
        self._step_control = 70
        self._pace_freq = 2
        self._height = 105
        self._crossing_state = False

    def _play_ball_task(self, leg_id):
        if leg_id != 2 or not self._dog:
            self._play_ball = 0
            return
        motor_id = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43]
        angle_down = [-16, 66, 1, -17, 66, 1, -14, 74, 1, -14, 72, 1]
        motor_2 = [21, 22, 23]
        angle_hand = [-15, 51, 2, -13, 33, -1, -15, 64, 3, -19, 59, 0]
        angle_play_2 = [10, 0, 0]
        try:
            if self._play_ball:
                self._dog.motor_speed(100)
                self._dog.motor(motor_id, angle_down)
                time.sleep(0.3)
            if self._play_ball:
                self._dog.motor(motor_id, angle_hand)
                time.sleep(0.2)
            if self._play_ball:
                self._dog.motor_speed(255)
                time.sleep(0.01)
            if self._play_ball:
                self._dog.motor(motor_2, angle_play_2)
                time.sleep(0.3)
            if self._play_ball:
                self._dog.motor(motor_id, angle_hand)
                time.sleep(0.3)
            if self._play_ball:
                self._dog.motor_speed(100)
                self._dog.motor(motor_id, angle_down)
                time.sleep(0.3)
            if self._play_ball:
                self._dog.action(0xFF)
        except Exception as e:
            print(f"[joystick] play_ball 异常: {e}", flush=True)
        self._height = 105
        self._play_ball = 0

    def process_event(self, name, value):
        if not self._dog:
            return
        # 跨障模式下只响应 SELECT/START
        if self._crossing_state and name not in ("SELECT", "START"):
            return
        try:
            if name == "RK1_LEFT_RIGHT":
                v = -value
                fvalue = int(self._step_control * self.STEP_SCALE_Y * v)
                self._dog.move("y", fvalue)
            elif name == "RK1_UP_DOWN":
                v = -value
                fvalue = int(self._step_control * self.STEP_SCALE_X * v)
                self._dog.move("x", fvalue)
            elif name == "RK2_UP_DOWN":
                v = -value
                if v == 0:
                    self._dog.turn(0)
                elif abs(v) > 0.9:
                    fvalue = int(self._my_map(self._step_control, 0, 100, 20, self.STEP_SCALE_Z * 100)) * (1 if v > 0 else -1)
                    self._dog.turn(fvalue)
            elif name == "RK2_LEFT_RIGHT":
                fvalue = int(value * 15)
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
                if value == 1 and not self._crossing_state and self._play_ball == 0:
                    self._play_ball = 2
                    t = threading.Thread(
                        target=self._play_ball_task,
                        args=(self._play_ball,),
                        name="play_ball_task",
                        daemon=True,
                    )
                    t.start()
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
                fvalue = v * self._step_control * self.STEP_SCALE_Y
                self._dog.move("y", fvalue)
            elif name == "WSAD_UP_DOWN":
                v = -value
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


# ===================== 自绘小控件（主题化） =====================

class StickIndicator(QWidget):
    """圆形摇杆指示器：外圈 + 十字 + 当前位置圆点。颜色全部来自主题。"""

    def __init__(self, label: str, size: int = 70, parent=None):
        super().__init__(parent)
        self._label = label
        self._x = 0.0
        self._y = 0.0
        self.setFixedSize(size, size + 14)

    def set_position(self, x: float, y: float):
        nx = max(-1.0, min(1.0, x))
        ny = max(-1.0, min(1.0, y))
        if abs(nx - self._x) > 0.01 or abs(ny - self._y) > 0.01:
            self._x, self._y = nx, ny
            self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        circle_h = self.height() - 14
        cx, cy = w / 2, circle_h / 2
        r = min(w, circle_h) / 2 - 3
        active = abs(self._x) > 0.05 or abs(self._y) > 0.05

        # 外圈：卡片风格（白底半透明 + 深蓝描边）
        border_c = QColor(*ColorRGB.text_primary, 55)
        bg_c = QColor(*ColorRGB.bg_card, 190)
        p.setPen(QPen(border_c, 1.5))
        p.setBrush(QBrush(bg_c))
        p.drawEllipse(QPointF(cx, cy), r, r)

        # 十字参考线：轨道色
        p.setPen(QPen(QColor(*ColorRGB.bg_track), 1))
        p.drawLine(int(cx - r + 3), int(cy), int(cx + r - 3), int(cy))
        p.drawLine(int(cx), int(cy - r + 3), int(cx), int(cy + r - 3))

        # 摇杆点 + 轨迹线
        dot_r = 5
        px = cx + self._x * (r - dot_r)
        py = cy - self._y * (r - dot_r)
        if active:
            p.setPen(QPen(QColor(T.accent), 1.5))
            p.drawLine(QPointF(cx, cy), QPointF(px, py))
        p.setPen(Qt.PenStyle.NoPen)
        dot_c = QColor(T.accent) if active else QColor(*ColorRGB.text_muted)
        p.setBrush(QBrush(dot_c))
        p.drawEllipse(QPointF(px, py), dot_r, dot_r)

        # 标签
        f = QFont()
        f.setPixelSize(Font.caption)
        f.setBold(True)
        p.setFont(f)
        label_c = QColor(T.text_secondary) if active else QColor(T.text_muted)
        p.setPen(label_c)
        p.drawText(0, circle_h, w, 14, Qt.AlignmentFlag.AlignCenter, self._label)


class TriggerBar(QWidget):
    """竖直触发键进度条（L2 / R2）。颜色全部来自主题。"""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._value = 0.0
        self.setFixedSize(20, 70)

    def set_value(self, v: float):
        nv = max(0.0, min(1.0, v))
        if abs(nv - self._value) > 0.01:
            self._value = nv
            self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        label_h = 12
        bar_y = label_h + 2
        bar_h = h - label_h - 2

        # 背景槽
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(*ColorRGB.bg_track))
        p.drawRoundedRect(0, bar_y, w, bar_h, Radius.sm, Radius.sm)

        # 填充条
        fill_h = int(bar_h * self._value)
        if fill_h > 0:
            fill_c = QColor(T.accent) if self._value > 0.95 else QColor(T.text_secondary)
            p.setBrush(fill_c)
            p.drawRoundedRect(0, bar_y + bar_h - fill_h, w, fill_h, Radius.sm, Radius.sm)

        # 标签
        f = QFont()
        f.setPixelSize(Font.caption)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(T.text_secondary))
        p.drawText(0, 0, w, label_h, Qt.AlignmentFlag.AlignCenter, self._label)


def _make_panel() -> QFrame:
    """主题化卡片面板（白底半透明圆角）。"""
    f = QFrame()
    f.setStyleSheet(
        f"QFrame {{ {T_qss.card()} }}"
    )
    return f


# ===================== PySide6 页面 =====================

class JoystickPage(AppFrame):
    """手柄控制界面，继承 AppFrame 获得主题背景 + 角标布局。"""

    # ABXY 使用主题语义色
    _ABXY_COLORS = {
        "A": T.success,
        "B": T.danger,
        "X": T.accent,
        "Y": T.warning,
    }

    def __init__(self):
        super().__init__()
        self._first_paint_logged = False

        self._js = JoystickReader(js_id=0)
        self._controller = DogController()

        self._last_btn_states: dict = {}
        self._last_axis_states: dict = {}
        self._exiting = False

        # 记录上次状态，避免每帧调用 setCornerHint 触发重排
        self._last_js_conn = None
        self._last_dog_avail = None

        # ---- 标题 & 角标 ----
        self.setTitle(_T("title"))
        self.setCornerHints(
            bl=(_T("hint_exit"), Asset.icon_back),
            br=_T("hint_action"),
        )

        # ---- 状态 chip（位于标题下方） ----
        self._js_chip = QLabel(_T("joystick_disconnected"), self)
        self._js_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._js_chip.setStyleSheet(T_qss.chip("danger"))

        self._dog_chip = QLabel(_T("dog_offline"), self)
        self._dog_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dog_chip.setStyleSheet(T_qss.chip("danger"))

        # ---- 左侧：摇杆区 ----
        self.stick_rk1 = StickIndicator("RK1", size=62)
        self.stick_rk2 = StickIndicator("RK2", size=62)
        self.stick_wsad = StickIndicator("WSAD", size=50)
        self.bar_l2 = TriggerBar("L2")
        self.bar_r2 = TriggerBar("R2")

        sticks_row = QHBoxLayout()
        sticks_row.setSpacing(Spacing.xs)
        sticks_row.setContentsMargins(0, 0, 0, 0)
        sticks_row.addWidget(self.bar_l2, 0, Qt.AlignmentFlag.AlignVCenter)
        sticks_row.addWidget(self.stick_rk1, 0, Qt.AlignmentFlag.AlignVCenter)
        sticks_row.addWidget(self.stick_rk2, 0, Qt.AlignmentFlag.AlignVCenter)
        sticks_row.addWidget(self.bar_r2, 0, Qt.AlignmentFlag.AlignVCenter)

        wsad_wrap = QHBoxLayout()
        wsad_wrap.setContentsMargins(0, 0, 0, 0)
        wsad_wrap.addStretch(1)
        wsad_wrap.addWidget(self.stick_wsad)
        wsad_wrap.addStretch(1)

        left_panel = _make_panel()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(Spacing.xs, Spacing.xs, Spacing.xs, Spacing.xs)
        left_layout.setSpacing(Spacing.xs)
        left_layout.addLayout(sticks_row)
        left_layout.addLayout(wsad_wrap)

        # ---- 右侧：按钮区 + 参数 ----
        self.btn_labels: dict = {}
        btn_grid = QGridLayout()
        btn_grid.setSpacing(3)
        btn_grid.setContentsMargins(0, 0, 0, 0)
        layout_def = [
            ("L1", 0, 0), ("R1", 0, 1), ("SELECT", 0, 2), ("START", 0, 3),
            ("X",  1, 0), ("Y",  1, 1), ("RK1",   1, 2), ("RK2",   1, 3),
            ("A",  2, 0), ("B",  2, 1), ("MODE",  2, 2),
        ]
        for name, row, col in layout_def:
            lbl = QLabel(name)
            lbl.setFixedSize(34, 17)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color = self._ABXY_COLORS.get(name)
            lbl.setProperty("_color", color)
            lbl.setStyleSheet(self._btn_style(False, color))
            self.btn_labels[name] = lbl
            btn_grid.addWidget(lbl, row, col)

        # 参数卡片区
        self.lbl_step = QLabel("70")
        self.lbl_pace = QLabel(_T("pace_med"))
        self.lbl_height = QLabel("105")
        self._param_labels = [self.lbl_step, self.lbl_pace, self.lbl_height]
        for v in self._param_labels:
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.setStyleSheet(T_qss.text("body", color=T.success))

        params_row = QHBoxLayout()
        params_row.setSpacing(Spacing.xs)
        params_row.setContentsMargins(0, 0, 0, 0)
        for tag_key, val_lbl in (
            (_T("step"), self.lbl_step),
            (_T("pace"), self.lbl_pace),
            (_T("height"), self.lbl_height),
        ):
            cell = QFrame()
            cell.setStyleSheet(
                f"QFrame {{"
                f"  background-color: {T.card_bg};"
                f"  border: 1px solid {T.card_border};"
                f"  border-radius: {Radius.sm}px;"
                f"}}"
            )
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(2, 2, 2, 2)
            cl.setSpacing(0)
            tag = QLabel(tag_key)
            tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tag.setStyleSheet(T_qss.text("caption"))
            cl.addWidget(tag)
            cl.addWidget(val_lbl)
            params_row.addWidget(cell)

        right_panel = _make_panel()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(Spacing.xs, Spacing.xs, Spacing.xs, Spacing.xs)
        right_layout.setSpacing(Spacing.xs)
        right_layout.addLayout(btn_grid)
        right_layout.addLayout(params_row)

        # ---- 内容容器（由 resizeEvent 定位） ----
        self._content = QWidget(self)
        body_layout = QHBoxLayout(self._content)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(Spacing.xs)
        body_layout.addWidget(left_panel, 11)
        body_layout.addWidget(right_panel, 9)

        # ---- 定时器 ----
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_ui)
        self._refresh_timer.start(60)

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_joystick)
        self._poll_timer.start(20)

        QTimer.singleShot(AUTO_EXIT_SEC * 1000, self.close)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._js.start()

    # ---- 按钮样式（使用主题色） ----
    @staticmethod
    def _btn_style(pressed: bool, color: str | None) -> str:
        if pressed:
            bg = color if color else T.accent
            return (
                f"color: {T.text_invert}; background-color: {bg};"
                f" border-radius: {Radius.sm}px;"
                f" font-size: {Font.caption}px; font-weight: bold;"
            )
        fg = color if color else T.text_muted
        return (
            f"color: {fg}; background-color: {T.card_bg};"
            f" border-radius: {Radius.sm}px;"
            f" font-size: {Font.caption}px; font-weight: bold;"
        )

    # ---- 布局（AppFrame 必须先调 super）----
    def resizeEvent(self, ev):
        super().resizeEvent(ev)   # 必须：AppFrame 负责标题 & 4 角重排
        w, h = self.width(), self.height()

        # 状态 chip 紧接标题下方
        chip_h = 16
        chip_y = 28
        chip_w = min(130, (w - Spacing.md * 2 - Spacing.xs) // 2)
        self._js_chip.setGeometry(Spacing.sm, chip_y, chip_w, chip_h)
        self._dog_chip.setGeometry(w - chip_w - Spacing.sm, chip_y, chip_w, chip_h)

        # 主内容区
        content_y = chip_y + chip_h + Spacing.xs
        content_h = h - content_y - 20   # 20px 留给底部角标
        self._content.setGeometry(
            Spacing.sm, content_y,
            w - Spacing.sm * 2, max(content_h, 80),
        )

    # ---- 手柄轮询 ----
    def _poll_joystick(self):
        if not self._js.connected:
            self._js.try_reconnect()
            return
        for name, value in self._js.button_states.items():
            last = self._last_btn_states.get(name, 0)
            if value != last:
                self._last_btn_states[name] = value
                self._controller.process_event(name, value)
        for name, value in self._js.axis_states.items():
            last = self._last_axis_states.get(name, 0.0)
            if abs(value - last) > 0.05 or (abs(last) > 0.05 and abs(value) <= 0.05):
                self._last_axis_states[name] = value
                self._controller.process_event(name, value)

    # ---- UI 刷新 ----
    def _refresh_ui(self):
        # 手柄状态 chip（仅状态变化时更新，避免频繁触发 setCornerHint relayout）
        js_conn = self._js.connected
        if js_conn != self._last_js_conn:
            self._last_js_conn = js_conn
            if js_conn:
                self._js_chip.setText(_T("joystick_connected"))
                self._js_chip.setStyleSheet(T_qss.chip("success"))
            else:
                self._js_chip.setText(_T("joystick_disconnected"))
                self._js_chip.setStyleSheet(T_qss.chip("danger"))

        # 机器狗状态 chip
        dog_avail = self._controller.dog_available
        if dog_avail != self._last_dog_avail:
            self._last_dog_avail = dog_avail
            if dog_avail:
                self._dog_chip.setText(_T("dog_ready"))
                self._dog_chip.setStyleSheet(T_qss.chip("success"))
            else:
                self._dog_chip.setText(_T("dog_offline"))
                self._dog_chip.setStyleSheet(T_qss.chip("danger"))

        # 摇杆位置
        ax = self._js.axis_states
        self.stick_rk1.set_position(ax.get("RK1_LEFT_RIGHT", 0), -ax.get("RK1_UP_DOWN", 0))
        self.stick_rk2.set_position(ax.get("RK2_LEFT_RIGHT", 0), -ax.get("RK2_UP_DOWN", 0))
        self.stick_wsad.set_position(ax.get("WSAD_LEFT_RIGHT", 0), -ax.get("WSAD_UP_DOWN", 0))
        self.bar_l2.set_value((ax.get("L2", -1.0) + 1) / 2)
        self.bar_r2.set_value((ax.get("R2", -1.0) + 1) / 2)

        # 按钮高亮
        btn_key_map = {
            "A": "A", "B": "B", "X": "X", "Y": "Y",
            "L1": "L1", "R1": "R1",
            "SELECT": "SELECT", "START": "START", "MODE": "MODE",
            "RK1": "BTN_RK1", "RK2": "BTN_RK2",
        }
        for display_name, internal_name in btn_key_map.items():
            lbl = self.btn_labels.get(display_name)
            if not lbl:
                continue
            pressed = bool(self._js.button_states.get(internal_name, 0))
            color = lbl.property("_color")
            lbl.setStyleSheet(self._btn_style(pressed, color))

        # 参数卡片值
        pace_names = {1: _T("pace_slow"), 2: _T("pace_med"), 3: _T("pace_fast")}
        self.lbl_step.setText(str(self._controller.step_control))
        self.lbl_pace.setText(pace_names.get(self._controller.pace_freq, _T("pace_med")))
        self.lbl_height.setText(str(self._controller.height))

    # ---- 首帧日志 ----
    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self._first_paint_logged:
            self._first_paint_logged = True
            mark("first paintEvent")
            print("[joystick] boot: " + self._stage_summary(), flush=True)

    def _stage_summary(self) -> str:
        lines = []
        prev = 0.0
        for name, ms in _stages:
            lines.append(f"{name}: {ms:.0f}ms (+{ms - prev:.0f})")
            prev = ms
        return " | ".join(lines)

    def keyPressEvent(self, ev: QKeyEvent):
        key = ev.key()
        if key in (Qt.Key.Key_Back, Qt.Key.Key_Escape, Qt.Key.Key_Q):
            if self._exiting:
                return
            self._exiting = True
            print("[joystick] KEY_BACK -> exit", flush=True)
            self.close()
            QApplication.instance().quit()

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
    apply_app_palette(app)       # 全局字体 + 调色板 + 滚动条
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

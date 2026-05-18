#!/usr/bin/env python3
"""
PySide6 雷达扫描 App — 由 Luwu OS launcher 启动。
在屏幕上绘制 YDLidar 雷达扫描数据。
物理按键：C=退出
"""
import sys
import os
import time
import signal
import math

# ---- 阶段计时 ----
T0 = time.monotonic()
_stages = []

def mark(name: str):
    ms = (time.monotonic() - T0) * 1000.0
    _stages.append((name, ms))
    print(f"[radar][+{ms:7.1f}ms] {name}", flush=True)

mark("python entry")

# ---- 添加 ydlidar SDK 路径（已迁移至 luwu-os/libs/ydlidar_sdk，解耦 XGO-PI-CM5）----
sys.path.insert(0, '/home/pi/luwu-os/libs/ydlidar_sdk')
import ydlidar

# ---- PySide6 ----
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QFont, QKeyEvent, QPainter, QColor, QPen, QBrush, QPixmap, QPaintEvent,
    QPainterPath, QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout

mark("imports done")

# ===================== i18n + 主题 =====================
if "/home/pi/luwu-os" not in sys.path:
    sys.path.insert(0, "/home/pi/luwu-os")
try:
    from libs.i18n import Translator as _Translator
    _T = _Translator({
        "cn": {
            "title": "雷达扫描",
            "init": "正在初始化雷达...",
            "corner_exit": "退出",
            "radar_disconnected": "雷达未连接",
            "radar_connected": "雷达已连接",
        },
        "en": {
            "title": "Lidar Scan",
            "init": "Initializing lidar...",
            "corner_exit": "Exit",
            "radar_disconnected": "Lidar not connected",
            "radar_connected": "Lidar connected",
        },
    })
except Exception:
    _T = lambda k, *a: k

from libs.theme import (  # noqa: E402
    apply_app_palette, Asset as T_Asset, Color as T_Color,
    Spacing, Radius, qss as T_qss,
)
from libs.ui import AppFrame  # noqa: E402

_APP_BG_IMAGE = "/home/pi/luwu-os/assets/images/app_bg.png"

# ===================== 常量 =====================
AUTO_EXIT_SEC = 120
MAX_DISPLAY_RANGE = 5.0  # 最大显示距离 (米)
RADAR_PORT = "/dev/ttyUSB0"
RADAR_BAUDRATE = 230400

# ===================== 雷达数据读取线程 =====================
class RadarReaderThread(QThread):
    """后台线程：读取 YDLidar 数据"""
    points_ready = Signal(list)        # 发送雷达点列表 [(distance, angle_deg), ...]
    radar_status = Signal(bool, str)   # 雷达状态: (connected, message)

    def __init__(self):
        super().__init__()
        self._running = False
        self.laser = None
        self.radar_connected = False

    def run(self):
        self._running = True
        self._init_radar()

        if not self.radar_connected:
            self.radar_status.emit(False, _T("radar_disconnected"))
            while self._running:
                time.sleep(2)
                self._init_radar()
                if self.radar_connected:
                    break
            if not self._running:
                return

        self.radar_status.emit(True, _T("radar_connected"))
        print("[radar] reader thread started")

        while self._running and ydlidar.os_isOk():
            try:
                scan = ydlidar.LaserScan()
                if self.laser.doProcessSimple(scan):
                    points = []
                    for point in scan.points:
                        if point.range <= 0:
                            continue
                        angle_deg = math.degrees(point.angle)
                        distance = point.range
                        if 0.05 <= distance <= MAX_DISPLAY_RANGE:
                            points.append((distance, angle_deg))
                    self.points_ready.emit(points)
                else:
                    time.sleep(0.05)
                time.sleep(0.01)
            except Exception as e:
                print(f"[radar] read error: {e}")
                time.sleep(0.1)

        self._cleanup_radar()
        print("[radar] reader thread ended")

    def _init_radar(self):
        try:
            print("[radar] initializing YDLidar...")
            ydlidar.os_init()

            self.laser = ydlidar.CYdLidar()
            self.laser.setlidaropt(ydlidar.LidarPropSerialPort, RADAR_PORT)
            self.laser.setlidaropt(ydlidar.LidarPropIgnoreArray, "")
            self.laser.setlidaropt(ydlidar.LidarPropSerialBaudrate, RADAR_BAUDRATE)
            self.laser.setlidaropt(ydlidar.LidarPropLidarType, ydlidar.TYPE_TRIANGLE)
            self.laser.setlidaropt(ydlidar.LidarPropDeviceType, ydlidar.YDLIDAR_TYPE_SERIAL)
            self.laser.setlidaropt(ydlidar.LidarPropSampleRate, 4)
            self.laser.setlidaropt(ydlidar.LidarPropIntenstiyBit, 8)
            self.laser.setlidaropt(ydlidar.LidarPropFixedResolution, True)
            self.laser.setlidaropt(ydlidar.LidarPropReversion, False)
            self.laser.setlidaropt(ydlidar.LidarPropInverted, False)
            self.laser.setlidaropt(ydlidar.LidarPropAutoReconnect, True)
            self.laser.setlidaropt(ydlidar.LidarPropSingleChannel, False)
            self.laser.setlidaropt(ydlidar.LidarPropIntenstiy, True)
            self.laser.setlidaropt(ydlidar.LidarPropSupportMotorDtrCtrl, False)
            self.laser.setlidaropt(ydlidar.LidarPropSupportHeartBeat, False)
            self.laser.setlidaropt(ydlidar.LidarPropMaxAngle, 180.0)
            self.laser.setlidaropt(ydlidar.LidarPropMinAngle, -180.0)
            self.laser.setlidaropt(ydlidar.LidarPropMaxRange, 64.0)
            self.laser.setlidaropt(ydlidar.LidarPropMinRange, 0.05)
            self.laser.setlidaropt(ydlidar.LidarPropScanFrequency, 10.0)

            try:
                self.laser.enableGlassNoise(False)
                self.laser.enableSunNoise(False)
            except AttributeError:
                try:
                    self.laser.setGlassNoise(False)
                    self.laser.setSunNoise(False)
                except AttributeError:
                    pass

            ret = self.laser.initialize()
            if not ret:
                print(f"[radar] init failed: {self.laser.DescribeError()}")
                self.laser = None
                self.radar_connected = False
                return

            ret = self.laser.turnOn()
            if not ret:
                print(f"[radar] turnOn failed: {self.laser.DescribeError()}")
                self.laser.disconnecting()
                self.laser = None
                self.radar_connected = False
                return

            self.radar_connected = True
            print("[radar] YDLidar initialized and scanning")
        except Exception as e:
            print(f"[radar] init error: {e}")
            if self.laser:
                try:
                    self.laser.disconnecting()
                except Exception:
                    pass
            self.laser = None
            self.radar_connected = False

    def _cleanup_radar(self):
        if self.laser:
            try:
                self.laser.turnOff()
                self.laser.disconnecting()
                print("[radar] lidar turned off")
            except Exception as e:
                print(f"[radar] cleanup error: {e}")

    def stop(self):
        self._running = False


# ===================== 雷达画布（深色雷达屏，圆角 + 径向渐变） =====================
class RadarCanvas(QWidget):
    """自定义 QWidget — 用 QPainter 绘制一台仿真雷达屏。"""

    # 色板（与全局浅色主题协调，但屏内保持夜间雷达深色调）
    SCREEN_BG_INNER = QColor(12, 24, 56)        # 屏中心
    SCREEN_BG_OUTER = QColor(2, 6, 18)          # 屏边缘
    SCREEN_BORDER = QColor(58, 141, 255, 200)   # accent
    GRID_RING = QColor(58, 141, 255, 90)        # accent 半透明同心圆
    GRID_CROSS = QColor(58, 141, 255, 55)       # 十字线
    GRID_RAY = QColor(58, 141, 255, 35)         # 角度射线
    DIST_LABEL = QColor(140, 200, 255, 200)
    CENTER_DOT = QColor(58, 141, 255)
    INFO_TEXT = QColor(220, 232, 255)

    PT_NEAR = QColor(255, 90, 90)
    PT_MID = QColor(255, 215, 80)
    PT_FAR = QColor(120, 255, 160)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 220)
        self.radar_points = []
        self.radar_connected = False
        self.status_text = ""
        # 透明背景，AppFrame 桌面图透过来
        self.setStyleSheet("background: transparent;")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def update_points(self, points, connected, status):
        self.radar_points = points
        self.radar_connected = connected
        self.status_text = status
        self.update()

    def _polar_to_xy(self, distance, angle_deg, cx, cy, max_radius):
        angle_rad = math.radians(angle_deg)
        r = (distance / MAX_DISPLAY_RANGE) * max_radius
        x = cx + r * math.cos(angle_rad)
        y = cy - r * math.sin(angle_rad)
        return x, y

    def _pt_color(self, distance):
        if distance < 1.5:
            return self.PT_NEAR
        elif distance < 3.0:
            return self.PT_MID
        return self.PT_FAR

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            painter.end()
            return

        # ---- 屏体外形（圆角矩形） ----
        radius = 18
        screen_rect = QRectF(1, 1, w - 2, h - 2)
        path = QPainterPath()
        path.addRoundedRect(screen_rect, radius, radius)
        painter.setClipPath(path)

        # 屏内径向渐变背景
        cx_f = w / 2.0
        cy_f = h / 2.0
        grad = QRadialGradient(cx_f, cy_f, max(w, h) / 1.4)
        grad.setColorAt(0.0, self.SCREEN_BG_INNER)
        grad.setColorAt(1.0, self.SCREEN_BG_OUTER)
        painter.fillRect(screen_rect, QBrush(grad))

        # 未连接状态
        if not self.radar_connected:
            painter.setPen(self.INFO_TEXT)
            font = QFont()
            font.setPointSize(14)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.status_text)
            # 屏体描边
            painter.setClipping(False)
            pen = QPen(self.SCREEN_BORDER, 1.4)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(screen_rect, radius, radius)
            painter.end()
            return

        # ---- 坐标系 ----
        cx = int(cx_f)
        cy = int(cy_f)
        max_radius = max(40, min(w, h) // 2 - 16)

        # 同心圆 + 距离标签
        for i in range(1, 6):
            r = int(i * max_radius / 5)
            painter.setPen(QPen(self.GRID_RING, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            # 距离数字
            painter.setPen(self.DIST_LABEL)
            font = QFont()
            font.setPointSize(7)
            painter.setFont(font)
            painter.drawText(cx + r - 14, cy - 3, f"{i}m")

        # 十字线
        painter.setPen(QPen(self.GRID_CROSS, 1))
        painter.drawLine(0, cy, w, cy)
        painter.drawLine(cx, 0, cx, h)

        # 角度射线（每 30°）
        painter.setPen(QPen(self.GRID_RAY, 1))
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            ex = int(cx + max_radius * math.cos(rad))
            ey = int(cy - max_radius * math.sin(rad))
            painter.drawLine(cx, cy, ex, ey)

        # 中心点（带光晕）
        center_glow = QRadialGradient(cx, cy, 8)
        center_glow.setColorAt(0.0, QColor(58, 141, 255, 220))
        center_glow.setColorAt(1.0, QColor(58, 141, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(center_glow))
        painter.drawEllipse(cx - 8, cy - 8, 16, 16)
        painter.setBrush(QBrush(self.CENTER_DOT))
        painter.drawEllipse(cx - 2, cy - 2, 4, 4)

        # ---- 雷达点（带光晕） ----
        painter.setPen(Qt.PenStyle.NoPen)
        for dist, angle in self.radar_points:
            if dist > MAX_DISPLAY_RANGE:
                continue
            px, py = self._polar_to_xy(dist, angle, cx_f, cy_f, max_radius)
            color = self._pt_color(dist)
            # 外层光晕
            halo = QColor(color)
            halo.setAlpha(70)
            painter.setBrush(QBrush(halo))
            painter.drawEllipse(QPointF(px, py), 3.2, 3.2)
            # 实心核
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(px, py), 1.4, 1.4)

        # ---- 屏体描边 ----
        painter.setClipping(False)
        painter.setPen(QPen(self.SCREEN_BORDER, 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(screen_rect, radius, radius)

        painter.end()


# ===================== PySide6 主页面 =====================
class RadarPage(AppFrame):
    def __init__(self):
        super().__init__()
        # 覆盖背景为 app_bg.png（与 settings/AI/rc_mode/hotspot 同款）
        _pix = QPixmap(_APP_BG_IMAGE)
        if not _pix.isNull():
            self._bg_pix = _pix
            self.update()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._first_paint_logged = False

        # ---- 标题 ----
        self.setTitle(_T("title"))

        # ---- 顶部信息 chip 行：Points / Range / 状态 ----
        self.points_chip = QLabel("Points: 0", self)
        self.points_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.points_chip.setStyleSheet(T_qss.chip("muted"))

        self.range_chip = QLabel(f"Range: {MAX_DISPLAY_RANGE:.1f}m", self)
        self.range_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.range_chip.setStyleSheet(T_qss.chip("info"))

        self.status_chip = QLabel(_T("init"), self)
        self.status_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_chip.setStyleSheet(T_qss.chip("warning"))

        # ---- 雷达画布 ----
        self.radar_canvas = RadarCanvas(self)

        # ---- 中心容器 ----
        center = QWidget(self)
        center.setStyleSheet(T_qss.transparent())
        v = QVBoxLayout(center)
        v.setContentsMargins(Spacing.md, 0, Spacing.md, 0)
        v.setSpacing(Spacing.sm)

        # chip 行
        chip_row = QHBoxLayout()
        chip_row.setSpacing(Spacing.sm)
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip_row.addStretch(1)
        chip_row.addWidget(self.points_chip)
        chip_row.addWidget(self.range_chip)
        chip_row.addWidget(self.status_chip)
        chip_row.addStretch(1)
        v.addLayout(chip_row)
        v.addWidget(self.radar_canvas, 1)
        self._center = center

        # ---- 角标（修正按键：launcher 中 C = Key_Back）----
        self.setCornerHints(
            bl=(_T("corner_exit"), T_Asset.icon_back),
        )

        # ---- 自动退出 ----
        self._auto_exit_timer = QTimer(self)
        self._auto_exit_timer.timeout.connect(self.close)
        self._auto_exit_timer.start(AUTO_EXIT_SEC * 1000)

        # ---- 启动雷达读取线程 ----
        self._radar_thread = RadarReaderThread()
        self._radar_thread.points_ready.connect(self._on_points_ready)
        self._radar_thread.radar_status.connect(self._on_radar_status)
        self._radar_thread.start()

        print("[radar] page initialized")

    # ---- 布局 ----
    def resizeEvent(self, ev):
        super().resizeEvent(ev)  # AppFrame 负责背景与 4 角
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        top = max(30, h * 14 // 100)
        bottom = max(20, h * 8 // 100)
        self._center.setGeometry(0, top, w, h - top - bottom)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self._first_paint_logged:
            self._first_paint_logged = True
            mark("first paintEvent")

    # ---- 数据回调 ----
    def _on_points_ready(self, points):
        self.radar_canvas.update_points(points, True, "")
        self.points_chip.setText(f"Points: {len(points)}")

    def _on_radar_status(self, connected, message):
        if connected:
            self.status_chip.setText(message)
            self.status_chip.setStyleSheet(T_qss.chip("success"))
            self.radar_canvas.update_points(self.radar_canvas.radar_points, True, "")
        else:
            self.status_chip.setText(message)
            self.status_chip.setStyleSheet(T_qss.chip("danger"))
            self.radar_canvas.update_points([], False, message)

    # ---- 按键 ----
    def keyPressEvent(self, ev: QKeyEvent):
        key = ev.key()
        # launcher 中 C 键映射为 Key_Back；保留 Key_Up / Esc 作为兼容
        if key in (Qt.Key.Key_Back, Qt.Key.Key_Up, Qt.Key.Key_Escape):
            print(f"[radar] key={key} -> exit", flush=True)
            self.close()

    def closeEvent(self, ev):
        print("[radar] closing", flush=True)
        self._auto_exit_timer.stop()
        if self._radar_thread and self._radar_thread.isRunning():
            self._radar_thread.stop()
            self._radar_thread.wait(3000)
        super().closeEvent(ev)


# ===================== 入口 =====================
def main():
    signal.signal(signal.SIGINT, lambda *_: QApplication.instance().quit())
    signal.signal(signal.SIGTERM, lambda *_: QApplication.instance().quit())

    app = QApplication(sys.argv)
    apply_app_palette(app)
    mark("QApplication created")

    w = RadarPage()
    mark("widget constructed")

    w.showFullScreen()
    mark("showFullScreen returned")

    rc = app.exec()
    print(f"[radar] exit rc={rc}", flush=True)
    sys.exit(rc)


if __name__ == "__main__":
    main()

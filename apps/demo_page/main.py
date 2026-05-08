#!/usr/bin/env python3
"""
PyQt6 demo page launched by Luwu OS launcher.
Receives key events from gpio-keys kernel driver.
"""
import os
import sys
import time
import signal
import wave
import io
import struct
import math
import subprocess
import numpy as np
from picamera2 import Picamera2

# ---- Stage 0: process entry (very first thing we do) ----
T0 = time.monotonic()
_stages = []  # list[(name, abs_ms_since_T0)]


def mark(name: str):
    ms = (time.monotonic() - T0) * 1000.0
    _stages.append((name, ms))
    print(f"[pyqt_page][+{ms:7.1f}ms] {name}", flush=True)


def _play_beep(freq: int = 880, duration: float = 0.15, volume: float = 0.4):
    """Generate a sine-wave beep and play via aplay (dmix compatible)."""
    sample_rate = 16000
    n_samples = int(sample_rate * duration)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            val = int(volume * 32767 * math.sin(2 * math.pi * freq * i / sample_rate))
            wf.writeframes(struct.pack('<h', val))
    data = buf.getvalue()
    p = subprocess.Popen(
        ["aplay", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    p.stdin.write(data)
    p.stdin.close()


mark("python entry")

# ---- Stage 1: heavy import ----
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QKeyEvent, QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
mark("PyQt6 import done")


AUTO_EXIT_SEC = 30

# Physical button → key mapping (gpio-keys kernel driver):
#   A (top-left)     GPIO 17 → KEY_UP
#   B (top-right)    GPIO 22 → KEY_DOWN
#   C (bottom-left)  GPIO 23 → KEY_LEFT   <- used here as "exit"
#   D (bottom-right) GPIO 24 → KEY_RIGHT


class PyQtPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #0f1530; color: white;")
        self._first_paint_logged = False

        self.title = QLabel("Hello from PyQt6")
        f1 = QFont(); f1.setPointSize(16); f1.setBold(True)
        self.title.setFont(f1)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.info = QLabel("boot: -- ms")
        self.info.setStyleSheet("color: #8892c9; font-size: 11px;")
        self.info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info.setWordWrap(True)

        self.counter_label = QLabel("count: 0")
        fc = QFont(); fc.setPointSize(18); fc.setBold(True)
        self.counter_label.setFont(fc)
        self.counter_label.setStyleSheet("color: #18df6b;")
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.hint = QLabel("LEFT=exit | UP=record | RIGHT=beep | DOWN=cam")
        self.hint.setStyleSheet("color: #5c6a9c; font-size: 11px;")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.camera_label = QLabel("CAMERA OFF")
        self.camera_label.setFixedSize(240, 180)
        self.camera_label.setStyleSheet("background-color: black; border: 1px solid #333; color: #666;")
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_label.hide()

        # ---- 四角按键说明 ----
        corner_style = "color: #8892c9; font-size: 12px; background: transparent;"
        self.corner_tl = QLabel("Record", self)   # A 键: KEY_UP → 录音
        self.corner_tl.setStyleSheet(corner_style)
        self.corner_tr = QLabel("Camera", self)   # B 键: KEY_DOWN → 拍照
        self.corner_tr.setStyleSheet(corner_style)
        self.corner_tr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.corner_bl = QLabel("Exit", self)   # C 键: KEY_LEFT → 退出
        self.corner_bl.setStyleSheet(corner_style)
        self.corner_br = QLabel("Beep", self)   # D 键: KEY_RIGHT → 声音
        self.corner_br.setStyleSheet(corner_style)
        self.corner_br.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.info)
        layout.addWidget(self.counter_label)
        layout.addWidget(self.camera_label)
        layout.addWidget(self.hint)

        self.counter = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)  # 20 fps

        self.picam2 = None
        self.camera_active = False
        self.camera_timer = QTimer(self)
        self.camera_timer.timeout.connect(self._capture_frame)

        QTimer.singleShot(AUTO_EXIT_SEC * 1000, self.close)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def keyPressEvent(self, ev: QKeyEvent):
        if ev.key() == Qt.Key.Key_Left:
            print("[pyqt_page] KEY_LEFT pressed -> exit", flush=True)
            self.close()
        elif ev.key() == Qt.Key.Key_Right:
            print("[pyqt_page] KEY_RIGHT pressed -> beep", flush=True)
            _play_beep(freq=880)
        elif ev.key() == Qt.Key.Key_Up:
            self._record_and_play()
        elif ev.key() == Qt.Key.Key_Down:
            if not self.camera_active:
                self._start_camera()
            else:
                self._stop_camera()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        w, h = self.width(), self.height()
        pad = 16
        # 左侧靠左
        self.corner_tl.move(pad, pad)
        self.corner_bl.move(pad, h - self.corner_bl.height() - pad)
        # 右侧贴边：用 adjustSize 缩到文本宽度，再贴右边缘
        self.corner_tr.adjustSize()
        self.corner_br.adjustSize()
        self.corner_tr.move(w - self.corner_tr.width() - pad, pad)
        self.corner_br.move(w - self.corner_br.width() - pad, h - self.corner_br.height() - pad)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self._first_paint_logged:
            self._first_paint_logged = True
            mark("first paintEvent")
            # Build a summary string and show it on screen
            summary = self._stage_summary()
            self.info.setText(summary)
            print("[pyqt_page] boot breakdown:\n" + summary, flush=True)

    def _stage_summary(self) -> str:
        lines = []
        prev = 0.0
        for name, ms in _stages:
            lines.append(f"{name}: {ms:.0f}ms (+{ms - prev:.0f})")
            prev = ms
        return " | ".join(lines)

    def tick(self):
        self.counter += 1
        elapsed = time.monotonic() - T0
        self.counter_label.setText(f"count: {self.counter}   t={elapsed:5.1f}s")

    def closeEvent(self, ev):
        self._stop_camera()
        print("[pyqt_page] closing", flush=True)
        super().closeEvent(ev)

    def _record_and_play(self):
        self.hint.setText("recording 3s...")
        QApplication.processEvents()
        subprocess.run(
            ["arecord", "-D", "default", "-d", "3", "-f", "cd", "/tmp/luwu_rec.wav"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.hint.setText("playing back...")
        QApplication.processEvents()
        subprocess.run(
            ["aplay", "/tmp/luwu_rec.wav"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if self.camera_active:
            self.hint.setText("LEFT=exit | UP=record | RIGHT=beep | stop=cam")
        else:
            self.hint.setText("LEFT=exit | UP=record | RIGHT=beep | DOWN=cam")
        print("[pyqt_page] record+play done", flush=True)

    def _start_camera(self):
        try:
            self.camera_label.setText("starting...")
            self.camera_label.show()
            self.picam2 = Picamera2()
            config = self.picam2.create_preview_configuration(
                main={"size": (240, 180), "format": "RGB888"}
            )
            self.picam2.configure(config)
            self.picam2.start()
            self.camera_active = True
            self.camera_timer.start(66)  # ~15fps
            self.hint.setText("LEFT=exit | UP=record | RIGHT=beep | stop=cam")
            print("[pyqt_page] camera started", flush=True)
        except Exception as e:
            self.camera_label.setText(f"cam err: {e}")
            print(f"[pyqt_page] camera error: {e}", flush=True)
            self._stop_camera()

    def _stop_camera(self):
        self.camera_timer.stop()
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except Exception:
                pass
            self.picam2 = None
        self.camera_active = False
        self.camera_label.hide()
        self.hint.setText("LEFT=exit | UP=record | RIGHT=beep | DOWN=cam")
        print("[pyqt_page] camera stopped", flush=True)

    def _capture_frame(self):
        if not self.camera_active or self.picam2 is None:
            return
        try:
            frame = self.picam2.capture_array()
            h, w, c = frame.shape
            qimg = QImage(frame.data.tobytes(), w, h, w * c, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg).scaled(
                self.camera_label.width(), self.camera_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.camera_label.setPixmap(pixmap)
        except Exception as e:
            print(f"[pyqt_page] capture error: {e}", flush=True)


def main():
    signal.signal(signal.SIGINT, lambda *_: QApplication.instance().quit())
    signal.signal(signal.SIGTERM, lambda *_: QApplication.instance().quit())

    app = QApplication(sys.argv)
    mark("QApplication created")

    w = PyQtPage()
    mark("widget constructed")

    w.showFullScreen()
    mark("showFullScreen returned")

    rc = app.exec()
    print(f"[pyqt_page] exit rc={rc}", flush=True)
    sys.exit(rc)


if __name__ == "__main__":
    main()

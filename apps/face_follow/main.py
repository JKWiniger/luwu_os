#!/usr/bin/env python3
"""
Luwu OS - Face Follow App (PySide6)
人脸跟随: 检测人脸位置并控制机器狗头部/机身跟随

Physical button mapping (from luwu-keys.dts gpio-keys):
  A (GPIO17, top-left)     KEY_LEFT   → toggle camera mirror
  B (GPIO22, top-right)    KEY_RIGHT  → toggle robot control
  C (GPIO23, bottom-left)  KEY_BACK   → exit
  D (GPIO24, bottom-right) KEY_ENTER  → reset robot head
"""

import os
import sys
import signal

import cv2
from picamera2 import Picamera2

from PySide6.QtCore import Qt, QTimer, QSocketNotifier
from PySide6.QtGui import QKeyEvent, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QLabel

# ---- Paths ----
FACE_MODEL_PATH = "/home/pi/luwu-os/model/face_detection_yunet_2023mar.onnx"
KEYS_FIFO = "/tmp/luwu_keys.fifo"

# ---- Robot control ----
_xgo_dog = None
_robot_available = False

try:
    from xgolib import XGO
    _xgo_dog = XGO()
    _robot_available = True
    print("[face_follow] XGO 初始化成功", flush=True)
except Exception as e:
    print(f"[face_follow] XGO 初始化失败: {e} (仅预览模式)", flush=True)
    _robot_available = False


def robot_attitude(axis_list, angle_list):
    """安全地调整机器人姿态"""
    if _robot_available and _xgo_dog:
        try:
            _xgo_dog.attitude(axis_list, angle_list)
        except Exception as e:
            print(f"[face_follow] robot_attitude error: {e}", flush=True)


def robot_reset():
    """重置机器人姿态"""
    if _robot_available and _xgo_dog:
        try:
            _xgo_dog.reset()
        except Exception as e:
            print(f"[face_follow] robot_reset error: {e}", flush=True)


# ============================================================================
# Face Follow Widget
# ============================================================================
class FaceFollowWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #0a0a1a;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # ---- State ----
        self.robot_control_enabled = True
        self.mirror_enabled = True
        self.smooth_x = 0.0
        self.smooth_y = 0.0
        self.smooth_factor = 0.35  # 平滑系数

        # ---- Face detector (YuNet) ----
        self.face_detector = None
        self._init_face_detector()

        # ---- Camera ----
        self.picam2 = None
        self.camera_active = False
        self.camera_size = (320, 240)

        # ---- Camera display ----
        self.camera_label = QLabel(self)
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_label.setStyleSheet("background-color: black;")

        # ---- Status label ----
        self.status_label = QLabel("人脸跟随", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "color: #18df6b; font-size: 16px; font-weight: bold; "
            "background-color: rgba(0,0,0,0.6); padding: 4px 10px; border-radius: 4px;"
        )

        # ---- Info label (bottom) ----
        self.info_label = QLabel("", self)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet(
            "color: #aabbee; font-size: 12px; "
            "background-color: rgba(0,0,0,0.5); padding: 3px 8px; border-radius: 4px;"
        )

        # ---- Corner hints ----
        corner_style = (
            "color: #ffffff; font-size: 13px; font-weight: bold; "
            "background-color: rgba(0,0,0,0.65); padding: 3px 8px; border-radius: 4px;"
        )
        self.corner_tl = QLabel("A:镜像", self)
        self.corner_tl.setStyleSheet(corner_style)
        self.corner_tr = QLabel("B:控制", self)
        self.corner_tr.setStyleSheet(corner_style)
        self.corner_tr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.corner_bl = QLabel("C:退出", self)
        self.corner_bl.setStyleSheet(corner_style)
        self.corner_br = QLabel("D:重置", self)
        self.corner_br.setStyleSheet(corner_style)
        self.corner_br.setAlignment(Qt.AlignmentFlag.AlignRight)

        # ---- Timers ----
        self.camera_timer = QTimer(self)
        self.camera_timer.timeout.connect(self._process_frame)

        self._frame_count = 0

        # ---- Keys FIFO ----
        self._keys_fd = -1
        self._keys_notifier = None
        self._setup_keys_fifo()

        # ---- Start ----
        QTimer.singleShot(100, self._start_camera)

    # ---- Face detector init ----
    def _init_face_detector(self):
        if not os.path.exists(FACE_MODEL_PATH):
            print(f"[face_follow] 人脸检测模型不存在: {FACE_MODEL_PATH}", flush=True)
            return
        try:
            self.face_detector = cv2.FaceDetectorYN.create(
                FACE_MODEL_PATH, "", (320, 240), 0.7, 0.3, 5000
            )
            print("[face_follow] FaceDetectorYN 初始化成功", flush=True)
        except Exception as e:
            print(f"[face_follow] FaceDetectorYN 初始化失败: {e}", flush=True)

    # ---- Camera lifecycle ----
    def _start_camera(self):
        try:
            self.picam2 = Picamera2()
            config = self.picam2.create_preview_configuration(
                main={"size": self.camera_size, "format": "RGB888"}
            )
            self.picam2.configure(config)
            self.picam2.start()
            self.camera_active = True
            self.camera_timer.start(50)  # ~20 fps
            print("[face_follow] Camera started", flush=True)
        except Exception as e:
            self.status_label.setText(f"Camera error: {e}")
            print(f"[face_follow] Camera error: {e}", flush=True)

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

    # ---- Frame processing ----
    def _process_frame(self):
        if not self.camera_active or self.picam2 is None:
            return

        try:
            # Capture frame
            img = self.picam2.capture_array()
            # img is in RGB888 format
            img = cv2.flip(img, 1) if self.mirror_enabled else img

            h, w = img.shape[:2]

            # Resize detector input size if needed
            if self.face_detector is not None:
                self.face_detector.setInputSize((w, h))
                _, faces = self.face_detector.detect(img)

                target_x, target_y = 0.0, 0.0
                found_face = False

                if faces is not None and len(faces) > 0:
                    # Take the largest face
                    best_face = max(faces, key=lambda f: f[2] * f[3])
                    x1, y1, fw, fh = (
                        int(best_face[0]), int(best_face[1]),
                        int(best_face[2]), int(best_face[3])
                    )

                    # Face center
                    face_cx = x1 + fw // 2
                    face_cy = y1 + fh // 2

                    # Calculate offset from image center
                    # Center of image is (w/2, h/2)
                    raw_x = face_cx - w / 2  # positive = face is to the right
                    raw_y = face_cy - h / 2  # positive = face is below center

                    # Map to robot angle range
                    # yaw: -25 to 25 degrees (left-right)
                    # pitch: -15 to 15 degrees (up-down)
                    target_x = max(min(raw_x / (w / 2) * 25, 25), -25)
                    target_y = max(min(-raw_y / (h / 2) * 15, 15), -15)

                    found_face = True

                    # Draw bounding box
                    cv2.rectangle(img, (x1, y1), (x1 + fw, y1 + fh), (0, 255, 100), 2)

                    # Draw center point
                    cv2.circle(img, (face_cx, face_cy), 4, (0, 255, 255), -1)

                    # Draw crosshair at image center
                    cv2.line(img, (w // 2 - 15, h // 2), (w // 2 + 15, h // 2), (100, 100, 255), 1)
                    cv2.line(img, (w // 2, h // 2 - 15), (w // 2, h // 2 + 15), (100, 100, 255), 1)

                # Smooth movement
                if found_face:
                    self.smooth_x = self.smooth_x * (1 - self.smooth_factor) + target_x * self.smooth_factor
                    self.smooth_y = self.smooth_y * (1 - self.smooth_factor) + target_y * self.smooth_factor
                else:
                    # Gradually return to center when no face detected
                    self.smooth_x *= 0.92
                    self.smooth_y *= 0.92

                # Control robot
                if self.robot_control_enabled:
                    sy = round(self.smooth_y)
                    sx = round(self.smooth_x)
                    if abs(sx) > 1 or abs(sy) > 1:
                        robot_attitude(['y', 'p'], [sx, sy])

                # Update info
                ctrl_status = "控制:ON" if self.robot_control_enabled else "控制:OFF"
                mirror_status = "镜像:ON" if self.mirror_enabled else "镜像:OFF"
                face_status = f"Detected:({target_x:.0f},{target_y:.0f})" if found_face else "No face"

                self.info_label.setText(f"{ctrl_status} | {mirror_status} | {face_status}")
            else:
                cv2.line(img, (w // 2 - 15, h // 2), (w // 2 + 15, h // 2), (100, 100, 255), 1)
                cv2.line(img, (w // 2, h // 2 - 15), (w // 2, h // 2 + 15), (100, 100, 255), 1)

                cv2.putText(img, "Face Detector N/A", (10, h // 2),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 1)

            # Convert to QPixmap and display
            h, w, c = img.shape
            qimg = QImage(img.data.tobytes(), w, h, w * c, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg).scaled(
                self.camera_label.width(),
                self.camera_label.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.camera_label.setPixmap(pixmap)

        except Exception as e:
            print(f"[face_follow] Frame error: {e}", flush=True)

    # ---- Keys FIFO from launcher ----
    def _setup_keys_fifo(self):
        try:
            self._keys_fd = os.open(KEYS_FIFO, os.O_RDONLY | os.O_NONBLOCK)
            self._keys_notifier = QSocketNotifier(self._keys_fd, QSocketNotifier.Type.Read, self)
            self._keys_notifier.activated.connect(self._on_key_fifo)
            print("[face_follow] Keys FIFO opened", flush=True)
        except Exception as e:
            print(f"[face_follow] Keys FIFO error: {e}", flush=True)

    def _on_key_fifo(self, fd: int):
        try:
            data = os.read(fd, 32)
            if data:
                for line in data.decode().strip().split('\n'):
                    if line.strip():
                        qt_key = int(line.strip())
                        ev = QKeyEvent(QKeyEvent.Type.KeyPress, qt_key, Qt.KeyboardModifier.NoModifier)
                        QApplication.postEvent(self, ev)
        except Exception as e:
            print(f"[face_follow] key fifo read error: {e}", flush=True)

    # ---- Key events ----
    def keyPressEvent(self, ev: QKeyEvent):
        key = ev.key()
        if key == Qt.Key.Key_Back:   # C → exit
            print("[face_follow] KEY_BACK (C) → exit", flush=True)
            self.close()
        elif key == Qt.Key.Key_Left:  # A → toggle mirror
            print("[face_follow] KEY_LEFT (A) → toggle mirror", flush=True)
            self.mirror_enabled = not self.mirror_enabled
        elif key == Qt.Key.Key_Right:  # B → toggle robot control
            print("[face_follow] KEY_RIGHT (B) → toggle robot control", flush=True)
            self.robot_control_enabled = not self.robot_control_enabled
        elif key == Qt.Key.Key_Enter or key == Qt.Key.Key_Return:  # D → reset
            print("[face_follow] KEY_ENTER (D) → reset robot", flush=True)
            robot_reset()
            self.smooth_x = 0.0
            self.smooth_y = 0.0

    # ---- Resize ----
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        w, h = self.width(), self.height()
        pad = 12

        # Camera fills entire screen
        self.camera_label.setGeometry(0, 0, w, h)

        # Status label at top center
        self.status_label.adjustSize()
        sw = self.status_label.width()
        self.status_label.move((w - sw) // 2, pad)

        # Info label at bottom center
        self.info_label.adjustSize()
        iw = self.info_label.width()
        self.info_label.move((w - iw) // 2, h - self.info_label.height() - pad - 4)

        # Corners
        self.corner_tl.raise_()
        self.corner_tl.adjustSize()
        self.corner_tl.move(pad, pad + 4)
        self.corner_bl.raise_()
        self.corner_bl.adjustSize()
        self.corner_bl.move(pad, h - self.corner_bl.height() - pad - 4)

        self.corner_tr.raise_()
        self.corner_tr.adjustSize()
        self.corner_tr.move(w - self.corner_tr.width() - pad, pad + 4)
        self.corner_br.raise_()
        self.corner_br.adjustSize()
        self.corner_br.move(w - self.corner_br.width() - pad, h - self.corner_br.height() - pad - 4)

    # ---- Close ----
    def closeEvent(self, ev):
        self._stop_camera()
        if self._keys_notifier:
            self._keys_notifier.setEnabled(False)
        if self._keys_fd >= 0:
            try:
                os.close(self._keys_fd)
            except Exception:
                pass
        robot_reset()
        print("[face_follow] closing", flush=True)
        super().closeEvent(ev)


# ============================================================================
# Entry point
# ============================================================================
def main():
    signal.signal(signal.SIGINT, lambda *_: QApplication.instance().quit())
    signal.signal(signal.SIGTERM, lambda *_: QApplication.instance().quit())

    app = QApplication(sys.argv)
    w = FaceFollowWidget()
    w.showFullScreen()

    rc = app.exec()
    print(f"[face_follow] exit rc={rc}", flush=True)


if __name__ == "__main__":
    main()

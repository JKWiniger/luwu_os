#!/usr/bin/env python3
"""
Luwu OS Settings App (PySide6)
Settings list with 5 items: SN, Volume, Language, Contact Us, App Download
Launched by the Luwu launcher via FIFO/preload mechanism.
"""
import os
import sys
import json
import uuid
import signal
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QFont, QKeyEvent, QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QStackedWidget,
)

# ---- Paths ----
APP_DIR = Path(__file__).resolve().parent
PICS_DIR = APP_DIR / "pics"
LANGUAGE_INI = APP_DIR / "language.ini"
VOLUME_INI = APP_DIR / "volume.ini"
CN_LA = APP_DIR / "cn.la"
EN_LA = APP_DIR / "en.la"

# ---- Language helpers ----
def load_language():
    """Load current language file based on language.ini"""
    try:
        with open(LANGUAGE_INI, "r") as f:
            lang = f.read().strip()
    except Exception:
        lang = "cn"
    la_path = CN_LA if lang == "cn" else EN_LA
    try:
        with open(la_path, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def get_lang_code():
    try:
        with open(LANGUAGE_INI, "r") as f:
            return f.read().strip()
    except Exception:
        return "cn"

# ---- SN helpers ----
def get_sn_short():
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("Serial"):
                    return line.split(":")[1].strip().upper()[-8:]
    except Exception:
        return ""
    return ""

def get_mac_address():
    mac = uuid.getnode()
    return ''.join(['{:02x}'.format((mac >> i) & 0xff) for i in reversed(range(0, 48, 8))]).upper()

# ---- Volume helpers ----
def read_volume():
    try:
        with open(VOLUME_INI, "r") as f:
            return int(f.read().strip())
    except Exception:
        return 50

def write_volume(vol):
    with open(VOLUME_INI, "w") as f:
        f.write(str(vol))
    # Try pactl first, fallback to amixer
    if os.system("which pactl > /dev/null 2>&1") == 0:
        os.system("pactl set-sink-volume @DEFAULT_SINK@ " + str(vol) + "%")
    else:
        os.system("amixer set Playback " + str(vol) + "% > /dev/null 2>&1")

# ---- Color constants ----
COLOR_BG = QColor(15, 21, 48)
COLOR_CARD = QColor(25, 32, 65)
COLOR_SELECT = QColor(100, 80, 220)
COLOR_WHITE = QColor(255, 255, 255)
COLOR_GRAY = QColor(140, 145, 180)
COLOR_PURPLE = QColor(120, 100, 240)
COLOR_UNSELECT = QColor(50, 55, 80)
COLOR_GREEN = QColor(0, 229, 255)

# ============================================================================
# Setting Item Data
# ============================================================================
SETTING_ITEMS = [
    {"id": "sn",          "icon": "icon_sn.png",       "label_key": "SN"},
    {"id": "volume",      "icon": "volume.png",        "label_key": "VOLUME"},
    {"id": "language",    "icon": "language.png",      "label_key": "LANGUAGE"},
    {"id": "contact_us",  "icon": "qrcode.png",        "label_key": "CONTACT"},
    {"id": "app_download","icon": "app_download.png",  "label_key": "APPDOWN"},
]

# ============================================================================
# SettingsListPage
# ============================================================================
class SettingsListPage(QWidget):
    def __init__(self, stack: QStackedWidget):
        super().__init__()
        self.stack = stack
        self.selected_idx = 0
        self.scroll_offset = 0
        self.la = load_language()

        self.setStyleSheet("background-color: #0f1530;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Corner hints
        hint_style = "color: #8892c9; font-size: 12px; background: transparent;"
        self.corner_tl = QLabel("A:上移", self)
        self.corner_tl.setStyleSheet(hint_style)
        self.corner_tr = QLabel("B:下移", self)
        self.corner_tr.setStyleSheet(hint_style)
        self.corner_tr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.corner_bl = QLabel("C:返回", self)
        self.corner_bl.setStyleSheet(hint_style)
        self.corner_br = QLabel("D:进入", self)
        self.corner_br.setStyleSheet(hint_style)
        self.corner_br.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Item widgets
        self.item_widgets = []
        for i, item in enumerate(SETTING_ITEMS):
            w = self._make_item_widget(item, i)
            self.item_widgets.append(w)

        self.update_selection()

    def _make_item_widget(self, item, index):
        """Create a container widget for a settings list item."""
        container = QWidget(self)
        container.setFixedSize(250, 26)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(6, 1, 6, 1)
        layout.setSpacing(6)

        # Icon
        icon_label = QLabel()
        icon_path = str(PICS_DIR / item["icon"])
        pix = QPixmap(icon_path)
        if not pix.isNull():
            pix = pix.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_label.setPixmap(pix)
        icon_label.setFixedSize(20, 20)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("background: transparent;")
        icon_label.setObjectName(f"icon_{index}")
        layout.addWidget(icon_label)

        # Label
        label_key = item["label_key"]
        text = self.la.get("DEMOEN", {}).get(label_key, label_key)
        text_label = QLabel(text)
        text_font = QFont()
        text_font.setPointSize(11)
        text_label.setFont(text_font)
        text_label.setStyleSheet("color: #cccccc; background: transparent;")
        text_label.setObjectName(f"text_{index}")
        layout.addWidget(text_label)

        layout.addStretch()

        # Arrow indicator
        arrow = QLabel(">")
        arrow_font = QFont()
        arrow_font.setPointSize(11)
        arrow.setFont(arrow_font)
        arrow.setStyleSheet("color: #555; background: transparent;")
        arrow.setObjectName(f"arrow_{index}")
        layout.addWidget(arrow)

        container.setObjectName(f"item_{index}")
        container.setStyleSheet(f"#item_{index} {{ background-color: {COLOR_CARD.name()}; border-radius: 6px; }}")
        return container

    def update_selection(self):
        """Update visual styles based on selected index."""
        for i, w in enumerate(self.item_widgets):
            sel = (i == self.selected_idx)
            self._update_item_style(w, i, sel)

    def _update_item_style(self, container, idx, selected):
        if selected:
            container.setStyleSheet(
                f"#item_{idx} {{ background-color: {COLOR_SELECT.name()}; border-radius: 6px; }}"
            )
            text_label = container.findChild(QLabel, f"text_{idx}")
            if text_label:
                text_label.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: bold; background: transparent;")
            arrow = container.findChild(QLabel, f"arrow_{idx}")
            if arrow:
                arrow.setStyleSheet("color: #ffffff; font-size: 11px; background: transparent;")
        else:
            container.setStyleSheet(
                f"#item_{idx} {{ background-color: {COLOR_CARD.name()}; border-radius: 6px; }}"
            )
            text_label = container.findChild(QLabel, f"text_{idx}")
            if text_label:
                text_label.setStyleSheet("color: #cccccc; font-size: 11px; background: transparent;")
            arrow = container.findChild(QLabel, f"arrow_{idx}")
            if arrow:
                arrow.setStyleSheet("color: #555555; font-size: 11px; background: transparent;")

    def move_selection(self, delta):
        new_idx = self.selected_idx + delta
        total = len(SETTING_ITEMS)
        if new_idx < 0:
            new_idx = 0
        if new_idx >= total:
            new_idx = total - 1
        if new_idx == self.selected_idx:
            return
        self.selected_idx = new_idx

        # Adjust scroll offset to keep selected item visible
        visible_count = self._visible_count()
        if self.selected_idx < self.scroll_offset:
            self.scroll_offset = self.selected_idx
        elif self.selected_idx >= self.scroll_offset + visible_count:
            self.scroll_offset = self.selected_idx - visible_count + 1

        self._relayout_items()
        self.update_selection()

    def _visible_count(self):
        """How many items fit in the list area."""
        h = self.height()
        if h == 0:
            return len(SETTING_ITEMS)
        top_margin = 28   # reserve for top corner hints
        bottom_margin = 28
        avail = h - top_margin - bottom_margin
        item_h = 26
        gap = 4
        count = (avail + gap) // (item_h + gap)
        return max(1, min(count, len(SETTING_ITEMS)))

    def _relayout_items(self):
        """Position visible items, hide others."""
        w = self.width()
        if w == 0:
            return
        h = self.height()
        top_margin = 28
        item_h = 26
        gap = 4
        visible_count = self._visible_count()
        x = (w - 250) // 2

        for i, item_w in enumerate(self.item_widgets):
            if self.scroll_offset <= i < self.scroll_offset + visible_count:
                rel = i - self.scroll_offset
                y = top_margin + rel * (item_h + gap)
                item_w.setGeometry(x, y, 250, item_h)
                item_w.show()
            else:
                item_w.hide()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        w, h = self.width(), self.height()

        # Keep selection in visible range after resize
        visible_count = self._visible_count()
        if self.selected_idx < self.scroll_offset:
            self.scroll_offset = self.selected_idx
        elif self.selected_idx >= self.scroll_offset + visible_count:
            self.scroll_offset = max(0, self.selected_idx - visible_count + 1)

        self._relayout_items()

        # Corner hints
        pad = 12
        self.corner_tl.move(pad, pad)
        self.corner_tr.adjustSize()
        self.corner_tr.move(w - self.corner_tr.width() - pad, pad)
        self.corner_bl.move(pad, h - self.corner_bl.height() - pad)
        self.corner_br.adjustSize()
        self.corner_br.move(w - self.corner_br.width() - pad, h - self.corner_br.height() - pad)

    def keyPressEvent(self, ev: QKeyEvent):
        if ev.key() == Qt.Key.Key_Up or ev.key() == Qt.Key.Key_Left:
            self.move_selection(-1)
        elif ev.key() == Qt.Key.Key_Down or ev.key() == Qt.Key.Key_Right:
            self.move_selection(1)
        elif ev.key() == Qt.Key.Key_Return:
            item_id = SETTING_ITEMS[self.selected_idx]["id"]
            self.stack.navigate_to(item_id)
        elif ev.key() == Qt.Key.Key_Back:
            QApplication.instance().quit()

    def refresh_language(self):
        self.la = load_language()
        self.update_selection()


# ============================================================================
# SN Page
# ============================================================================
class SNPage(QWidget):
    def __init__(self, stack: QStackedWidget):
        super().__init__()
        self.stack = stack
        self.setStyleSheet("background-color: #0f1530;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.la = load_language()

        # Title
        self.title_label = QLabel("Device Info", self)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #ffffff; background: transparent;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # SN display
        full_sn = f"SN: {get_sn_short()}{get_mac_address()}"
        self.sn_label = QLabel(full_sn, self)
        sn_font = QFont()
        sn_font.setPointSize(14)
        self.sn_label.setFont(sn_font)
        self.sn_label.setStyleSheet("color: #00E5FF; background: transparent;")
        self.sn_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Corner hints
        hint_style = "color: #8892c9; font-size: 12px; background: transparent;"
        self.corner_bl = QLabel("Back", self)
        self.corner_bl.setStyleSheet(hint_style)
        self.corner_br = QLabel("Exit", self)
        self.corner_br.setStyleSheet(hint_style)
        self.corner_br.setAlignment(Qt.AlignmentFlag.AlignRight)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        w, h = self.width(), self.height()
        self.title_label.setGeometry(0, 40, w, 30)
        self.sn_label.setGeometry(0, h // 2 - 20, w, 30)
        pad = 12
        self.corner_bl.move(pad, h - self.corner_bl.height() - pad)
        self.corner_br.adjustSize()
        self.corner_br.move(w - self.corner_br.width() - pad, h - self.corner_br.height() - pad)

    def keyPressEvent(self, ev: QKeyEvent):
        if ev.key() == Qt.Key.Key_Back or ev.key() == Qt.Key.Key_Left:
            self.stack.navigate_to("list")
        elif ev.key() == Qt.Key.Key_Return:
            QApplication.instance().quit()


# ============================================================================
# Volume Page
# ============================================================================
class VolumePage(QWidget):
    def __init__(self, stack: QStackedWidget):
        super().__init__()
        self.stack = stack
        self.volume = read_volume()
        self.la = load_language()
        self.setStyleSheet("background-color: #0f1530;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Title
        self.title_label = QLabel("Volume", self)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #ffffff; background: transparent;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Volume percent label
        self.percent_label = QLabel(f"{self.volume}%", self)
        pct_font = QFont()
        pct_font.setPointSize(20)
        pct_font.setBold(True)
        self.percent_label.setFont(pct_font)
        self.percent_label.setStyleSheet("color: #00E5FF; background: transparent;")
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Saved hint (hidden by default)
        self.saved_label = QLabel("", self)
        saved_font = QFont()
        saved_font.setPointSize(12)
        self.saved_label.setFont(saved_font)
        self.saved_label.setStyleSheet("color: #00E5FF; background: transparent;")
        self.saved_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.saved_label.hide()

        # Corner hints
        hint_style = "color: #8892c9; font-size: 12px; background: transparent;"
        self.corner_tl = QLabel("-5%", self)
        self.corner_tl.setStyleSheet(hint_style)
        self.corner_tr = QLabel("+5%", self)
        self.corner_tr.setStyleSheet(hint_style)
        self.corner_tr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.corner_bl = QLabel("Save", self)
        self.corner_bl.setStyleSheet(hint_style)
        self.corner_br = QLabel("Exit", self)
        self.corner_br.setStyleSheet(hint_style)
        self.corner_br.setAlignment(Qt.AlignmentFlag.AlignRight)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Volume bar background
        bar_x, bar_y = 40, h // 2 + 10
        bar_w, bar_h = w - 80, 20
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(COLOR_UNSELECT)
        painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 6, 6)

        # Volume bar fill
        fill_w = int(bar_w * self.volume / 100)
        if fill_w > 0:
            painter.setBrush(COLOR_PURPLE)
            painter.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 6, 6)

        # Tick marks
        painter.setPen(QPen(QColor(80, 85, 120), 1))
        for i in range(0, 101, 25):
            tx = bar_x + int(bar_w * i / 100)
            painter.drawLine(tx, bar_y, tx, bar_y + bar_h)

        painter.end()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        w, h = self.width(), self.height()
        self.title_label.setGeometry(0, 30, w, 30)
        self.percent_label.setGeometry(0, h // 2 - 40, w, 30)
        self.saved_label.setGeometry(0, h - 60, w, 25)
        pad = 12
        self.corner_tl.move(pad, pad)
        self.corner_tr.adjustSize()
        self.corner_tr.move(w - self.corner_tr.width() - pad, pad)
        self.corner_bl.move(pad, h - self.corner_bl.height() - pad)
        self.corner_br.adjustSize()
        self.corner_br.move(w - self.corner_br.width() - pad, h - self.corner_br.height() - pad)

    def update_volume_display(self):
        self.percent_label.setText(f"{self.volume}%")
        self.update()

    def keyPressEvent(self, ev: QKeyEvent):
        if ev.key() == Qt.Key.Key_Left:
            if self.volume > 0:
                self.volume = max(0, self.volume - 5)
                self.update_volume_display()
        elif ev.key() == Qt.Key.Key_Right:
            if self.volume < 100:
                self.volume = min(100, self.volume + 5)
                self.update_volume_display()
        elif ev.key() == Qt.Key.Key_Back:
            # Save and go back
            write_volume(self.volume)
            saved_text = self.la.get("VOLUME", {}).get("SAVED", "Saved!")
            self.saved_label.setText(saved_text)
            self.saved_label.show()
            QTimer.singleShot(800, lambda: self.stack.navigate_to("list"))
        elif ev.key() == Qt.Key.Key_Return:
            QApplication.instance().quit()


# ============================================================================
# Language Page
# ============================================================================
class LanguagePage(QWidget):
    def __init__(self, stack: QStackedWidget):
        super().__init__()
        self.stack = stack
        self.content = get_lang_code()
        self.la = load_language()
        self.setStyleSheet("background-color: #0f1530;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Title
        self.title_label = QLabel("Language", self)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #ffffff; background: transparent;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Option buttons (drawn manually)
        self.cn_selected = (self.content == "cn")
        self.en_selected = (self.content == "en")

        # Saved hint
        self.saved_label = QLabel("", self)
        saved_font = QFont()
        saved_font.setPointSize(12)
        self.saved_label.setFont(saved_font)
        self.saved_label.setStyleSheet("color: #00E5FF; background: transparent;")
        self.saved_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.saved_label.hide()

        # Corner hints
        hint_style = "color: #8892c9; font-size: 12px; background: transparent;"
        self.corner_tl = QLabel("CN", self)
        self.corner_tl.setStyleSheet(hint_style)
        self.corner_tr = QLabel("EN", self)
        self.corner_tr.setStyleSheet(hint_style)
        self.corner_tr.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.corner_bl = QLabel("Save", self)
        self.corner_bl.setStyleSheet(hint_style)
        self.corner_br = QLabel("Exit", self)
        self.corner_br.setStyleSheet(hint_style)
        self.corner_br.setAlignment(Qt.AlignmentFlag.AlignRight)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        btn_w, btn_h = 100, 50
        total_w = btn_w * 2 + 20
        start_x = (w - total_w) // 2
        btn_y = h // 2 - btn_h // 2

        cn_font = QFont()
        cn_font.setPointSize(16)
        cn_font.setBold(True)
        en_font = QFont()
        en_font.setPointSize(16)
        en_font.setBold(True)

        # CN button
        if self.cn_selected:
            painter.setBrush(COLOR_PURPLE)
        else:
            painter.setBrush(COLOR_UNSELECT)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(start_x, btn_y, btn_w, btn_h, 10, 10)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(cn_font)
        painter.drawText(QRect(start_x, btn_y, btn_w, btn_h), Qt.AlignmentFlag.AlignCenter, "CN")

        # EN button
        en_x = start_x + btn_w + 20
        if self.en_selected:
            painter.setBrush(COLOR_PURPLE)
        else:
            painter.setBrush(COLOR_UNSELECT)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(en_x, btn_y, btn_w, btn_h, 10, 10)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(en_font)
        painter.drawText(QRect(en_x, btn_y, btn_w, btn_h), Qt.AlignmentFlag.AlignCenter, "EN")

        painter.end()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        w, h = self.width(), self.height()
        self.title_label.setGeometry(0, 30, w, 30)
        self.saved_label.setGeometry(0, h - 60, w, 25)
        pad = 12
        self.corner_tl.move(pad, pad)
        self.corner_tr.adjustSize()
        self.corner_tr.move(w - self.corner_tr.width() - pad, pad)
        self.corner_bl.move(pad, h - self.corner_bl.height() - pad)
        self.corner_br.adjustSize()
        self.corner_br.move(w - self.corner_br.width() - pad, h - self.corner_br.height() - pad)

    def keyPressEvent(self, ev: QKeyEvent):
        if ev.key() == Qt.Key.Key_Left:
            self.content = "cn"
            self.cn_selected = True
            self.en_selected = False
            self.update()
        elif ev.key() == Qt.Key.Key_Right:
            self.content = "en"
            self.cn_selected = False
            self.en_selected = True
            self.update()
        elif ev.key() == Qt.Key.Key_Back:
            # Save language and restart
            with open(LANGUAGE_INI, "w") as f:
                f.write(self.content)
            saved_text = self.la.get("LANGUAGE", {}).get("SAVED", "Saved!")
            self.saved_label.setText(saved_text)
            self.saved_label.show()
            QTimer.singleShot(1500, lambda: self._do_restart())
        elif ev.key() == Qt.Key.Key_Return:
            QApplication.instance().quit()

    def _do_restart(self):
        # Quit app; launcher will restart preload process automatically
        QApplication.instance().quit()


# ============================================================================
# QR Code Page (Contact Us / App Download)
# ============================================================================
class QRPage(QWidget):
    def __init__(self, stack: QStackedWidget, qr_image: str, email: str = None):
        super().__init__()
        self.stack = stack
        self.qr_image = qr_image
        self.email = email
        self.la = load_language()
        self.qr_pixmap = None
        self.setStyleSheet("background-color: #0f1530;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Load QR image
        qr_path = str(PICS_DIR / qr_image)
        pix = QPixmap(qr_path)
        if not pix.isNull():
            self.qr_pixmap = pix

        # Corner hints
        hint_style = "color: #8892c9; font-size: 12px; background: transparent;"
        self.corner_bl = QLabel("Back", self)
        self.corner_bl.setStyleSheet(hint_style)
        self.corner_br = QLabel("Exit", self)
        self.corner_br.setStyleSheet(hint_style)
        self.corner_br.setAlignment(Qt.AlignmentFlag.AlignRight)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if self.qr_pixmap and not self.qr_pixmap.isNull():
            max_size = min(w - 60, h - 100, 200)
            scaled = self.qr_pixmap.scaled(
                max_size, max_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            qr_x = (w - scaled.width()) // 2
            qr_y = (h - scaled.height() - 30) // 2
            painter.drawPixmap(qr_x, qr_y, scaled)

            # Email below QR
            if self.email:
                email_font = QFont()
                email_font.setPointSize(10)
                painter.setFont(email_font)
                painter.setPen(COLOR_GREEN)
                email_rect = QRect(0, qr_y + scaled.height() + 5, w, 20)
                painter.drawText(email_rect, Qt.AlignmentFlag.AlignCenter, self.email)

        painter.end()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        w, h = self.width(), self.height()
        pad = 12
        self.corner_bl.move(pad, h - self.corner_bl.height() - pad)
        self.corner_br.adjustSize()
        self.corner_br.move(w - self.corner_br.width() - pad, h - self.corner_br.height() - pad)

    def keyPressEvent(self, ev: QKeyEvent):
        if ev.key() == Qt.Key.Key_Back or ev.key() == Qt.Key.Key_Left:
            self.stack.navigate_to("list")
        elif ev.key() == Qt.Key.Key_Return:
            QApplication.instance().quit()


# ============================================================================
# SettingsStack (manages all pages)
# ============================================================================
class SettingsStack(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #0f1530;")

        self.list_page = SettingsListPage(self)
        self.sn_page = SNPage(self)
        self.volume_page = VolumePage(self)
        self.language_page = LanguagePage(self)
        self.contact_page = QRPage(self, " xgorobot_wx.png", "hello@xgorobot.com")
        self.download_page = QRPage(self, "app_down_qr.png")

        self.addWidget(self.list_page)     # 0
        self.addWidget(self.sn_page)       # 1
        self.addWidget(self.volume_page)   # 2
        self.addWidget(self.language_page) # 3
        self.addWidget(self.contact_page)  # 4
        self.addWidget(self.download_page) # 5

        self.setCurrentIndex(0)
        self.page_map = {
            "list":         0,
            "sn":           1,
            "volume":       2,
            "language":     3,
            "contact_us":   4,
            "app_download": 5,
        }

    def navigate_to(self, page_id: str):
        idx = self.page_map.get(page_id, 0)
        self.setCurrentIndex(idx)
        widget = self.widget(idx)
        if widget:
            widget.setFocus()
            # Refresh language on certain pages
            if hasattr(widget, 'refresh_language'):
                widget.refresh_language()
            if hasattr(widget, 'la'):
                widget.la = load_language()
                if hasattr(widget, 'update'):
                    widget.update()


# ============================================================================
# SettingsApp container
# ============================================================================
class SettingsApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #0f1530;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = SettingsStack()
        layout.addWidget(self.stack)

        self.setFocusProxy(self.stack.list_page)

    def keyPressEvent(self, ev: QKeyEvent):
        # Forward all keys to current page
        current = self.stack.currentWidget()
        if current:
            current.keyPressEvent(ev)


# ============================================================================
# main() entry point (called by preload_app.py)
# ============================================================================
def main():
    signal.signal(signal.SIGINT, lambda *_: QApplication.instance().quit())
    signal.signal(signal.SIGTERM, lambda *_: QApplication.instance().quit())

    app = QApplication(sys.argv)

    w = SettingsApp()
    w.showFullScreen()

    rc = app.exec()
    print(f"[settings] exit rc={rc}", flush=True)
    sys.exit(rc)


if __name__ == "__main__":
    main()

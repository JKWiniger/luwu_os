"""文字组件——角色化的 QLabel 子类。

子应用应直接使用这些组件，避免自己 setStyleSheet 设字号字色。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from ..theme import qss


class _RoleLabel(QLabel):
    _role: str = "body"

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(qss.text(self._role))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

    def setColor(self, color: str) -> None:
        """临时换色（如状态文字 success/danger）。"""
        self.setStyleSheet(qss.text(self._role, color=color))


class TitleLabel(_RoleLabel):
    _role = "title"


class SubtitleLabel(_RoleLabel):
    _role = "subtitle"


class BodyLabel(_RoleLabel):
    _role = "body"


class HintLabel(_RoleLabel):
    _role = "hint"


class CaptionLabel(_RoleLabel):
    _role = "caption"

"""卡片容器与左标签右值的信息行。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout

from ..theme import Spacing, qss
from .text import BodyLabel, HintLabel


class CardPanel(QFrame):
    """白底半透明圆角容器，用于把若干 InfoRow / Label 分组。"""

    def __init__(self, parent=None, selected: bool = False):
        super().__init__(parent)
        self._selected = selected
        self.setStyleSheet(qss.card(selected))

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(Spacing.md, Spacing.sm, Spacing.md, Spacing.sm)
        self._layout.setSpacing(Spacing.xs)

    def addWidget(self, widget) -> None:
        self._layout.addWidget(widget)

    def addLayout(self, layout) -> None:
        self._layout.addLayout(layout)

    def setSelected(self, selected: bool) -> None:
        if selected == self._selected:
            return
        self._selected = selected
        self.setStyleSheet(qss.card(selected))

    def isSelected(self) -> bool:
        return self._selected


class InfoRow(QFrame):
    """左标签右值的一行（SN/IP/版本号等）。"""

    def __init__(self, label: str, value: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(qss.transparent())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.sm)

        self._label = HintLabel(label, self)
        self._value = BodyLabel(value, self)
        self._value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self._label)
        layout.addStretch()
        layout.addWidget(self._value)

    def setLabel(self, text: str) -> None:
        self._label.setText(text)

    def setValue(self, text: str) -> None:
        self._value.setText(text)

    def label(self) -> HintLabel:
        return self._label

    def value(self) -> BodyLabel:
        return self._value

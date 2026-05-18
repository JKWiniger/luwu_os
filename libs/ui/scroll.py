"""主题化垂直滚动列表。"""
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from ..theme import Spacing, qss


class ScrollList(QScrollArea):
    """透明背景的纵向滚动列表，配合 CardPanel 使用。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._content = QWidget()
        self._content.setStyleSheet(qss.transparent())
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(Spacing.sm, Spacing.sm, Spacing.sm, Spacing.sm)
        self._layout.setSpacing(Spacing.xs)
        self.setWidget(self._content)

    # --- public helpers
    def addItem(self, widget) -> None:
        self._layout.addWidget(widget)

    def addStretch(self) -> None:
        self._layout.addStretch()

    def clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def contentLayout(self) -> QVBoxLayout:
        return self._layout

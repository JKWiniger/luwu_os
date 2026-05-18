"""状态色块（success/warning/danger/info/muted）。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from ..theme import qss


class StatusChip(QLabel):
    """状态色块。常用于连接状态、网络状态等。"""

    VALID_STATES = ("success", "warning", "danger", "info", "muted")

    def __init__(self, text: str = "", state: str = "info", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state = state if state in self.VALID_STATES else "info"
        self.setStyleSheet(qss.chip(self._state))

    def setState(self, state: str) -> None:
        if state not in self.VALID_STATES:
            return
        self._state = state
        self.setStyleSheet(qss.chip(state))

    def state(self) -> str:
        return self._state

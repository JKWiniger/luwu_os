"""摄像头类应用基类。

摄像头画面 :attr:`video` 全屏铺设，4 角提示和标题浮于其上。
使用方式::

    class MyCameraPage(CameraOverlay):
        def __init__(self):
            super().__init__()
            self.setCornerHints(bl=("退出", Asset.icon_back))
        def update_frame(self, qimage):
            self.video.setPixmap(QPixmap.fromImage(qimage))
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from .frame import AppFrame


class CameraOverlay(AppFrame):
    """摄像头基类——video 全屏置底，主题角标浮在上层。"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.video = QLabel(self)
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 摄像头画面区域强制黑底，避免无帧时露出主题浅色显得突兀
        self.video.setStyleSheet("background-color: #000000;")
        self.video.lower()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.video.setGeometry(0, 0, self.width(), self.height())
        # 重置堆叠顺序：video 在最底，4 角和标题在最上
        self.video.lower()
        for c in self._corners.values():
            c.raise_()
        if self._title.isVisible():
            self._title.raise_()

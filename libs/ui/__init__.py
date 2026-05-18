"""luwu-os PySide6 通用 UI 组件。

子应用应直接使用这些组件，禁止再各自挑色/挑字号/手写 setStyleSheet。
"""
from .camera import CameraOverlay
from .card import CardPanel, InfoRow
from .chip import StatusChip
from .frame import AppFrame, CornerHint, CornerKey
from .scroll import ScrollList
from .text import BodyLabel, CaptionLabel, HintLabel, SubtitleLabel, TitleLabel

__all__ = [
    "AppFrame",
    "CornerHint",
    "CornerKey",
    "TitleLabel",
    "SubtitleLabel",
    "BodyLabel",
    "HintLabel",
    "CaptionLabel",
    "CardPanel",
    "InfoRow",
    "StatusChip",
    "ScrollList",
    "CameraOverlay",
]

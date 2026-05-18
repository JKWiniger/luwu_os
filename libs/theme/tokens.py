"""Design tokens（颜色/字号/间距/圆角/资源路径）。

集中变量，便于一处改动全 app 跟随。子应用不要自己挑色或定字号，
统一通过本模块取值。
"""
from pathlib import Path

# launcher 的资产作为子应用的视觉资产源，保证视觉一致
_LAUNCHER_ASSETS = Path("/home/pi/luwu-os/launcher/assets")


class Color:
    """浅色调色盘（与 launcher 浅色背景一致）。"""

    # 文字
    text_primary = "#1a3a6e"      # 与 launcher gridview 文字一致
    text_secondary = "#5d7299"
    text_muted = "#8aa1c7"
    text_invert = "#ffffff"

    # 卡片
    card_bg = "rgba(255, 255, 255, 200)"
    card_border = "rgba(26, 58, 110, 40)"
    card_selected_bg = "rgba(58, 141, 255, 230)"
    card_selected_border = "#3a8dff"

    # 主色 / 语义色
    accent = "#3a8dff"
    success = "#18a957"
    warning = "#e69900"
    danger = "#d6453d"

    # 兜底背景（背景图加载失败时）
    bg_solid = "#eaf0fb"


class Font:
    """字号（像素），与 launcher 14px 正文对齐。"""

    family = "Noto Sans CJK SC"
    title = 18       # 页面大标题
    subtitle = 15    # 子标题
    body = 14        # 正文
    hint = 12        # 提示
    caption = 11     # 角标/说明


class Spacing:
    xs = 4
    sm = 8
    md = 12
    lg = 16
    xl = 20


class Radius:
    sm = 6
    md = 10
    lg = 14


class Asset:
    """复用 launcher 资产，避免视觉断层。"""

    bg_image = str(_LAUNCHER_ASSETS / "bg_macos.png")
    bg_image_alt = str(_LAUNCHER_ASSETS / "bg_macos_1.png")

    icon_back = str(_LAUNCHER_ASSETS / "icon_back.png")
    icon_enter = str(_LAUNCHER_ASSETS / "icon_enter.png")
    icon_left = str(_LAUNCHER_ASSETS / "icon_left.png")
    icon_right = str(_LAUNCHER_ASSETS / "icon_right.png")


# 预留 DARK 主题接口（暂未实现，后续可在此分支基础上做夜间模式）
THEME_MODE = "light"

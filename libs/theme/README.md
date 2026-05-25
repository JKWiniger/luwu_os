## PySide 子应用主题层

为 `apps/` 下的所有 PySide 子应用提供与 launcher（C++）视觉同源的浅色主题：
共用 `bg_macos.png` 背景图、深蓝主文字 `#1a3a6e`、iOS 风格圆角卡片与角标图标。

> **铁律**：子应用里**不要再写硬编码颜色字符串**。所有颜色/字号/间距/资源路径从本模块取值；
> 一切样式通过主题函数（`libs/theme/qss.py`）拼出，不要再写 `"color: #xxxxxx;"`。

---

### 1 · 目录结构

```
libs/
├── theme/                # 设计 token + QSS 工厂
│   ├── tokens.py         # Color / Font / Spacing / Radius / Asset
│   ├── qss.py            # text() / card() / chip() / transparent() / app_root() / app_palette()
│   └── __init__.py       # apply_app_palette(app) 入口
└── ui/                   # 通用组件
    ├── frame.py          # AppFrame + CornerHint + CornerKey
    ├── text.py           # TitleLabel / SubtitleLabel / BodyLabel / HintLabel / CaptionLabel
    ├── card.py           # CardPanel / InfoRow
    ├── chip.py           # StatusChip
    ├── scroll.py         # ScrollList
    └── camera.py         # CameraOverlay（摄像头类 app 用：全屏画面 + 主题化叠层）
```

---

### 2 · 新建 app 模板（最小骨架）

复制粘贴即可运行。已经包含背景图、4 角提示和入口调色板。

```python
import sys
from pathlib import Path
LUWU_ROOT = Path("/opt/luwu-os/luwu-os")
if str(LUWU_ROOT) not in sys.path:
    sys.path.insert(0, str(LUWU_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from libs.theme import apply_app_palette, Asset, Color as T
from libs.ui import AppFrame, TitleLabel, BodyLabel, HintLabel


class HelloPage(AppFrame):
    def __init__(self):
        super().__init__()
        self.setTitle("Hello Luwu")
        self.body = BodyLabel("正文文字示例，自动用主题字号与深蓝主色。", self)
        self.setCornerHints(
            tl="选项",
            tr=("帮助", Asset.icon_right),
            bl=("返回", Asset.icon_back),
            br=("确认", Asset.icon_enter),
        )

    def resizeEvent(self, ev):
        super().resizeEvent(ev)       # 必须调用：父类负责标题与 4 角布局
        w, h = self.width(), self.height()
        self.body.setGeometry(20, h // 2 - 12, w - 40, 24)

    def keyPressEvent(self, ev: QKeyEvent):
        if ev.key() == Qt.Key.Key_Back:
            QApplication.instance().quit()


def main():
    app = QApplication(sys.argv)
    apply_app_palette(app)          # 一行启用全局主题
    w = HelloPage()
    w.showFullScreen()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

---

### 3 · Token 速查表

| 分组 | Key | 值 | 用途 |
|---|---|---|---|
| **文字** | `Color.text_primary` | `#1a3a6e` | 与 launcher 一致的主深蓝 |
|  | `Color.text_secondary` | `#5d7299` | 次级文字 |
|  | `Color.text_muted` | `#8aa1c7` | 提示/弱化 |
|  | `Color.text_invert` | `#ffffff` | 深色卡片上的反白 |
| **卡片** | `Color.card_bg` | `rgba(255,255,255,200)` | 默认卡片底 |
|  | `Color.card_border` | `rgba(26,58,110,40)` | 默认卡片边 |
|  | `Color.card_selected_bg` | `rgba(58,141,255,230)` | 选中卡片底 |
|  | `Color.card_selected_border` | `#3a8dff` | 选中卡片边 |
| **语义** | `Color.accent` | `#3a8dff` | 主交互蓝 |
|  | `Color.success` | `#18a957` | 成功 |
|  | `Color.warning` | `#e69900` | 警告 |
|  | `Color.danger` | `#d6453d` | 危险 |
| **字号(px)** | `Font.title / subtitle / body / hint / caption` | `18 / 15 / 14 / 12 / 11` | 与 launcher 14px 正文对齐 |
| **间距(px)** | `Spacing.xs / sm / md / lg / xl` | `4 / 8 / 12 / 16 / 20` | 4 的倍数节奏 |
| **圆角(px)** | `Radius.sm / md / lg` | `6 / 10 / 14` | sm=小控件 / md=卡片 / lg=容器 |
| **资源** | `Asset.bg_image` | launcher `bg_macos.png` | 子应用统一背景 |
|  | `Asset.icon_back / enter / left / right` | launcher 同名 png | 4 角提示图标 |

---

### 4 · 组件速查

| 组件 | 一句话用法 |
|---|---|
| `AppFrame` | **必用根容器**；自带背景图、4 角占位、标题。子类继承后 `resizeEvent` 必须先 `super().resizeEvent(ev)`。 |
| `TitleLabel` / `SubtitleLabel` / `BodyLabel` / `HintLabel` / `CaptionLabel` | 文字层级。统一字号 + 主色；可用 `.setColor(T.accent)` 临时改色。 |
| `CardPanel` | 圆角白底卡片容器；`CardPanel(self, selected=False)`。 |
| `InfoRow` | `InfoRow(label, value, parent)` 一行两列信息条，适合 About 类。 |
| `StatusChip` | 状态色块，`StatusChip("已连接", state="success")`，state ∈ `default/success/warning/danger`。 |
| `ScrollList` | 纵向滚动条；适合 wifi/蓝牙/列表类。 |
| `CameraOverlay` | 摄像头全屏背景 + 上层主题叠层（按钮/角标都走主题）。供 face/yolo 等摄像头三件套使用。 |
| `setCornerHints(tl=, tr=, bl=, br=)` | 一次性设 4 个角。值可为字符串或 `(text, icon_path)` 元组。 |

---

### 5 · AppFrame 角标布局规则

- 左角：**图标在左 + 文字在右**（如 `[←] Back`）
- 右角：**文字在左 + 图标在右**（如 `Confirm [⏎]`）
- 自动随窗口变化对齐 4 个角；子类无需再写定位代码。

---

### 6 · QSS 工厂（`libs.theme.qss`）

需要写局部样式时**只走这些函数**，不要拼颜色字符串：

```python
from libs.theme import qss as T_qss, Color as T

label.setStyleSheet(T_qss.text("body"))                       # 主题正文
label.setStyleSheet(T_qss.text("caption", color=T.accent))    # 主色 caption
panel.setStyleSheet(T_qss.card(selected=True))                # 选中卡片
chip.setStyleSheet(T_qss.chip("success"))                     # 成功色块
empty.setStyleSheet(T_qss.transparent())                      # 透明背景
```

---

### 7 · 启动入口（必加）

```python
from libs.theme import apply_app_palette
app = QApplication(sys.argv)
apply_app_palette(app)        # 全局字体 + 调色板
```

不加这一行，本机系统默认字体会带歪整套排版。

---

### 8 · 摄像头类 app 怎么用

摄像头画面**走全屏背景**（不要被卡片包住），上层叠加的按钮/提示/角标统一走主题：

```python
from libs.ui import CameraOverlay, TitleLabel

class FacePage(CameraOverlay):
    def __init__(self):
        super().__init__()
        self.tip = TitleLabel("对准人脸", self)
        self.setCornerHints(
            bl=("返回", Asset.icon_back),
            br=("拍摄", Asset.icon_enter),
        )
```

`CameraOverlay` 已经处理好：底层 QPixmap 摄像头帧、上层主题文字与角标的 z-order，
以及背景压暗以提高文字对比度。

---

### 9 · 参考样板：`apps/settings/`

settings 是首个完整套用本主题的样板。10 个子页面（list / about / sn / volume /
language / contact / download / time / shutdown / reboot）全部继承 `AppFrame`，
全文件 0 处硬编码颜色字符串，所有 `setStyleSheet` 都走 `T_qss.*` 主题函数。
推荐改造新 app 时直接对照 `apps/settings/main.py` 复用模式。

---

### 10 · 改造已有 app 的检查清单

- [ ] 顶部加 `sys.path.insert(0, "/opt/luwu-os/luwu-os")` + `from libs.theme import ...` + `from libs.ui import ...`
- [ ] 所有 `class XxxPage(QWidget)` → `class XxxPage(AppFrame)`
- [ ] 删除 `self.setStyleSheet("background-color: #...;")`
- [ ] 删除手写的 `corner_tl/tr/bl/br QLabel` 及其 `resizeEvent` 定位
- [ ] 改用 `self.setCornerHints(tl=..., tr=..., bl=..., br=...)`
- [ ] `QLabel + setFont + setStyleSheet("color: #xxx; ...")` 三连 → 换 `TitleLabel/SubtitleLabel/BodyLabel/HintLabel/CaptionLabel`
- [ ] 自绘 `QPainter` 中的 `QColor("#xxxxxx")` 全部走 `QColor(T_Color.xxx)`
- [ ] `main()` 加 `apply_app_palette(app)`
- [ ] `resizeEvent` 第一行必须 `super().resizeEvent(ev)`，否则角标不会定位
- [ ] 切语言钩子 `refresh_language(self)` 内重新调一次 `setCornerHints(...)`，保证多语言同步

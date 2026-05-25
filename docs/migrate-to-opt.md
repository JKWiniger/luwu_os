# luwu-os 迁移到 /opt 指南

## 目标

- 项目路径从 `/opt/luwu-os/luwu-os` → `/opt/luwu-os`
- systemd 服务从 `User=luwu` → 默认 root（用户名无关）
- 解决镜像刷机时用户改用户名导致服务启动失败的问题

## 改动范围

### 1. 统一路径变量

所有 Python 代码引入统一常量，不再硬编码：

```python
import os
LUWU_ROOT = os.environ.get("LUWU_ROOT", "/opt/luwu-os")
```

开发时：`export LUWU_ROOT=/opt/luwu-os/luwu-os`

### 2. 需要改的文件

| 文件 | 改动 |
|------|------|
| `apps/coding/config.py` | `LUWU_ROOT` 改用环境变量 |
| `apps/coding/coding_page.py` | `LUWU_ROOT` 改用环境变量 |
| `apps/coding/main.py` | `LUWU_ROOT` 改用环境变量 |
| `apps/radar/main.py` | `sys.path` + `_APP_BG_IMAGE` 改用环境变量 |
| `apps/sound_locate/main.py` | `sys.path` 改用环境变量 |
| `apps/network/main.py` | `LANGUAGE_INI` 改用环境变量 |
| `apps/settings/main.py` | `LANGUAGE_INI` 改用环境变量 |
| `apps/hotspot/main.py` | `SSID_FILE` 改用环境变量 |
| `apps/gamepad/mapping_server.py` | `MAPPINGS_FILE`、`_GP_DIR` 改用环境变量 |
| `libs/i18n.py` | `LUWU_ROOT` + `LANGUAGE_INI` + 字体路径 改用环境变量 |
| `libs/xgoedu-luwuos/xgoedu/edulib.py` | 字体路径、模型路径、xgoMusic/Pictures/Videos 改用环境变量 |
| `configs/detect_device.py` | `LUWU_ROOT` 改用环境变量 |
| `configs/hardware_autoconf.py` | 路径改用环境变量 |
| `configs/luwu-launcher.service` | 去掉 `User=luwu`，`ExecStart` 路径改为 `/opt/luwu-os/...` |
| `configs/luwu-splash.service` | 去掉 `User=luwu`，`ExecStart` 路径改为 `/opt/luwu-os/...` |
| `configs/luwu-hw-autoconf.service` | `ExecStart` 路径改为 `/opt/luwu-os/...` |
| `configs/luwu-splash.sh` | `BOOT_VIDEO`/`BOOT_IMAGE` 路径改为 `/opt/luwu-os/...` |
| `configs/kill-splash.sh` | 路径改为 `/opt/luwu-os/...` |
| `configs/install.sh` | 增加 `cp -r` 到 `/opt/luwu-os` + `chown` 步骤 |

### 3. 媒体目录重组

xgoedu 产生的媒体文件统一纳入项目内：

```
/opt/luwu-os/xgo-media/
├── music/      # 原 /opt/luwu-os/xgoMusic/
├── pictures/   # 原 /opt/luwu-os/xgoPictures/
└── videos/     # 原 /opt/luwu-os/xgoVideos/
```

### 4. systemd 服务改动

```ini
# luwu-launcher.service — 去掉 User=luwu，改用 root 默认
[Service]
Type=simple
ExecStartPre=/opt/luwu-os/configs/kill-splash.sh
ExecStart=/opt/luwu-os/launcher/build/luwu_launcher
Restart=always
RestartSec=3
```

```ini
# luwu-splash.service — 去掉 User=luwu
[Service]
Type=simple
ExecStart=/opt/luwu-os/configs/luwu-splash.sh
Restart=no
```

### 5. install.sh 新增步骤

```bash
# 拷贝项目到 /opt
cp -r /opt/luwu-os/luwu-os /opt/luwu-os
chown -R luwu:luwu /opt/luwu-os
chmod -R 755 /opt/luwu-os
```

## 注意事项

- 开发时设置环境变量 `LUWU_ROOT=/opt/luwu-os/luwu-os` 即可在原路径调试
- root 运行服务写入 `/opt` 无权限问题
- 用户数据（`lock.json`）仍在 `$HOME/.xgo-blockly/`，用 `os.path.expanduser()` 获取
- 不涉及 launcher C++ 源码改动（路径由 systemd `ExecStart` 控制）

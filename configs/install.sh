#!/bin/bash
# Luwu OS — 一键部署系统配置到树莓派
# 用法: sudo bash install.sh

set -e

echo "=== Luwu OS 系统配置部署 ==="

# 0. 确保 luwu 用户存在（树莓派官方 Imager 默认用户名是 pi，
#    这里按官方参考镜像的用户组配置创建，硬件访问权限需要这些组）
echo "[0/14] 检查 luwu 用户 ..."
if ! id -u luwu &>/dev/null; then
    useradd -m -s /bin/bash -G root,tty,dialout,sudo,audio,video,plugdev,input,spi,i2c,gpio luwu
    echo "  luwu 用户已创建，请设置密码："
    passwd luwu
    echo "  ✓ luwu 用户已创建"
else
    echo "  ✓ luwu 用户已存在，跳过创建"
fi

# 0a. 拷贝项目到 /opt/luwu-os（路径与用户名无关）
echo "[0a/14] 部署项目到 /opt/luwu-os ..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# 后续步骤里大量使用相对路径文件名 (boot-config.txt, *.service 等)，
# 必须先切到 configs/，否则无论从哪里调用本脚本都会找不到文件。
cd "$SCRIPT_DIR"
mkdir -p /opt/luwu-os
rm -rf /opt/luwu-os.old 2>/dev/null
[ -d /opt/luwu-os ] && mv /opt/luwu-os /opt/luwu-os.old
cp -r "$PROJECT_DIR" /opt/luwu-os
chown -R luwu:luwu /opt/luwu-os
chmod -R 755 /opt/luwu-os
# 创建 xgo-media 子目录
mkdir -p /opt/luwu-os/xgo-media/{music,pictures,videos}
chown -R luwu:luwu /opt/luwu-os/xgo-media
echo "  ✓ 项目已部署到 /opt/luwu-os"

# 0. 系统依赖
echo "[1/14] 更新软件源并安装系统依赖 ..."
apt update
apt install -y \
    python3-pip  python3-numpy python3-picamera2 python3-evdev \
    python3-flask python3-flask-socketio python3-opencv \
    mplayer alsa-utils ffmpeg libzbar0t64 portaudio19-dev \
    python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets
echo "  ✓ 系统依赖已安装"

# 0b. pip 依赖（apt 中没有的包 / 本地开发包）
echo "[0b/12] 安装 pip 依赖 ..."
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    pip3 install --break-system-packages -r "$PROJECT_DIR/requirements.txt" || echo "  ! pip 依赖安装警告（非致命）"
    echo "  ✓ pip 依赖已安装"
else
    echo "  ! requirements.txt 未找到，跳过"
fi

# 1. /boot/firmware/config.txt
echo "[2/14] 部署 /boot/firmware/config.txt ..."
cp boot-config.txt /boot/firmware/config.txt
echo "  ✓ 已写入"

# 2. gpio-keys 设备树覆盖层
echo "[3/14] 编译并部署 gpio-keys 设备树覆盖层 ..."
if ! command -v dtc &>/dev/null; then
    echo "  ! dtc 未安装，正在安装 device-tree-compiler ..."
    apt install -y device-tree-compiler
fi
dtc -@ -I dts -O dtb -o /boot/firmware/overlays/luwu-keys.dtbo luwu-keys.dts
echo "  ✓ luwu-keys.dtbo 已部署"

# 3. udev 规则 (fb-spi 软链接)
echo "[4/14] 部署 udev 规则 ..."
cp 99-fb-spi.rules /etc/udev/rules.d/
cp 99-gamepad-no-mouse.rules /etc/udev/rules.d/
udevadm control --reload-rules
udevadm trigger --subsystem-match=graphics
udevadm trigger --subsystem-match=input
echo "  ✓ 已生效 (fb-spi + 蓝牙手柄触摸板屏蔽)"

# 4. ALSA 音频配置 (dmix + dsnoop + 默认音量)
echo "[5/14] 部署 ALSA 音频配置 ..."
cp asound.conf /etc/asound.conf
# 恢复混音器状态（啸叫修复 + 默认音量 71%）
if [ -f asound.state ]; then
    alsactl restore -f asound.state
    cp asound.state /var/lib/alsa/asound.state
    echo "  ✓ 混音器状态已恢复"
else
    echo "  ! asound.state 不存在，使用当前系统音量"
fi
echo "  ✓ asound.conf 已写入"

# 5. systemd 服务
echo "[6/14] 部署 systemd 服务 ..."
cp luwu-splash.service /etc/systemd/system/
cp luwu-launcher.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable luwu-splash.service
systemctl enable luwu-launcher.service
echo "  ✓ 已启用"

# 5b. CM4 硬件自动识别服务
echo "[7/14] 部署 CM4 硬件自动识别服务 ..."
cp luwu-hw-autoconf.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable luwu-hw-autoconf.service
echo "  ✓ luwu-hw-autoconf.service 已启用 (开机自动检测 CM4 新/老硬件并切换 config.txt)"

# 6. 开机画面脚本权限
echo "[8/14] 设置开机画面脚本权限 ..."
chmod +x luwu-splash.sh
echo "  ✓ 已设置"

# 7. ext4 文件系统加固 — 防止断电丢文件
echo "[9/14] 文件系统加固 ..."
tune2fs -c 5 /dev/mmcblk0p2
echo "  ✓ fsck 每5次挂载自动执行"

# 内核命令行 rootflags=data=journal：文件数据也进日志，掉电不丢文件内容
if ! grep -q 'rootflags=data=journal' /boot/firmware/cmdline.txt; then
    sed -i 's|rootfstype=ext4|rootfstype=ext4 rootflags=data=journal|' /boot/firmware/cmdline.txt
fi
echo "  ✓ data=journal (rootflags) 已设置"

# 挂载选项 commit=1：journal 每秒刷盘，断电最多丢1秒数据
if ! grep -q 'commit=1' /etc/fstab; then
    sed -i 's|defaults,noatime|defaults,noatime,commit=1|' /etc/fstab
fi
echo "  ✓ commit=1 (fstab) 已设置"

# 8. 持久化系统日志 — 出问题可追溯
echo "[11/14] 持久化系统日志 ..."

# mask 掉树莓派 vendor 的 volatile 配置
mkdir -p /etc/systemd/journald.conf.d
ln -sf /dev/null /etc/systemd/journald.conf.d/40-rpi-volatile-storage.conf

# 配置持久化 + 50MB 上限
sed -i 's/#Storage=auto/Storage=persistent/' /etc/systemd/journald.conf
if ! grep -q "^SystemMaxUse=" /etc/systemd/journald.conf; then
    echo "SystemMaxUse=50M" >> /etc/systemd/journald.conf
fi

# 创建持久化目录并设置权限
mkdir -p /var/log/journal
chown root:systemd-journal /var/log/journal
chmod 2755 /var/log/journal

# 重启并 flush（systemd 252+ 必须 flush 才能从 volatile 切换到 persistent）
systemctl restart systemd-journald
journalctl --flush

echo "  ✓ 日志持久化已配置 (最大 50MB, 存于 /var/log/journal/)"

# 10. 欠压+电池联合监控 — 分级响应防误关机
echo "[12/14] 欠压+电池监控 ..."
chmod +x /opt/luwu-os/configs/luwu-undervolt-monitor.py
echo "  ✓ 欠压+电池监控由 launcher 内置 QTimer+QProcess 处理，无需 systemd 服务"

# 11. 完成
echo "[14/14] 部署完成。必须重启以加载新的设备树和防护配置: sudo reboot"
echo "=== 完毕 ==="

#!/bin/bash
# Luwu OS — 开机启动画面（视频/图片）
# 在 SPI 屏幕可用后立即显示，等待启动器接管

FB_DEV="/dev/fb-spi"
BOOT_VIDEO="/home/pi/luwu-os/launcher/assets/boot_splash.mp4"
BOOT_IMAGE="/home/pi/luwu-os/launcher/assets/bg_macos.png"
MPLAYER_PID=""

cleanup() {
    echo "[luwu-splash] cleaning up..."
    if [ -n "$MPLAYER_PID" ] && kill -0 "$MPLAYER_PID" 2>/dev/null; then
        kill "$MPLAYER_PID" 2>/dev/null || true
        wait "$MPLAYER_PID" 2>/dev/null || true
    fi
    # 确保没有残留的 mplayer 进程
    killall mplayer 2>/dev/null || true
    echo "[luwu-splash] done"
    exit 0
}

trap cleanup SIGTERM SIGINT SIGHUP

# 等待 SPI 屏幕就绪
echo "[luwu-splash] waiting for $FB_DEV ..."
while [ ! -e "$FB_DEV" ]; do
    sleep 0.1
done
echo "[luwu-splash] $FB_DEV ready"

# 播放开机画面
if [ -f "$BOOT_VIDEO" ]; then
    echo "[luwu-splash] playing boot video: $BOOT_VIDEO"
    mplayer -vo fbdev2:"$FB_DEV" -fs -zoom \
        -nolirc -noconfig all \
        -really-quiet \
        -loop 0 \
        "$BOOT_VIDEO" </dev/null &
    MPLAYER_PID=$!
elif [ -f "$BOOT_IMAGE" ]; then
    echo "[luwu-splash] showing boot image: $BOOT_IMAGE"
    mplayer -vo fbdev2:"$FB_DEV" -fs -zoom \
        -nolirc -noconfig all \
        -really-quiet \
        -loop 0 \
        "mf://$BOOT_IMAGE" -mf type=png </dev/null &
    MPLAYER_PID=$!
else
    echo "[luwu-splash] no boot media found, exiting"
    exit 1
fi

echo "[luwu-splash] mplayer PID=$MPLAYER_PID"

# 等待 mplayer 或被终止
wait $MPLAYER_PID 2>/dev/null || true

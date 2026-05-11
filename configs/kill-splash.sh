#!/bin/bash
# 停止 splash mplayer，等待其彻底退出后再让 Qt 启动
# 用于 luwu-launcher.service 的 ExecStartPre

for i in $(seq 1 30); do
    pid=$(pgrep -x mplayer 2>/dev/null)
    [ -z "$pid" ] && break
    kill -9 $pid 2>/dev/null || true
    sleep 0.2
done

# 额外等待 SPI 总线空闲
sleep 0.3
exit 0

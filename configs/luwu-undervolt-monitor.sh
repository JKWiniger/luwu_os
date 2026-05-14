#!/bin/bash
# Luwu OS 欠压监控 — 持续欠压超过10秒自动关机
THRESHOLD_SEC=10
CHECK_INTERVAL=2
MAX_COUNT=$((THRESHOLD_SEC / CHECK_INTERVAL))
UNDERVOLT_COUNT=0
STATUS_FILE="/tmp/luwu_undervolt_status"
log() { echo "[undervolt] $1" | systemd-cat -t undervolt -p warning; }
log "欠压监控启动，阈值=${THRESHOLD_SEC}秒"
while true; do
    THROTTLED=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
    CURRENT_UV=$((THROTTLED & 0x1))
    if [ "$CURRENT_UV" -eq 1 ]; then
        UNDERVOLT_COUNT=$((UNDERVOLT_COUNT + 1))
        ELAPSED=$((UNDERVOLT_COUNT * CHECK_INTERVAL))
        if [ "$UNDERVOLT_COUNT" -eq 1 ]; then
            log "⚠ 检测到欠压！将在 ${THRESHOLD_SEC} 秒后关机"
            wall "⚠ 电源电压不足，请检查电源！系统将在 ${THRESHOLD_SEC} 秒后关机。"
            echo "UNDERVOLT" > "$STATUS_FILE"
        fi
        if [ "$UNDERVOLT_COUNT" -ge "$MAX_COUNT" ]; then
            log "❌ 欠压持续 ${ELAPSED} 秒，执行保护关机"
            wall "❌ 电源电压持续不足，系统正在关机以保护文件。请更换电源后重启。"
            echo "SHUTDOWN" > "$STATUS_FILE"
            sleep 2
            shutdown -h now "欠压保护关机"
            exit 0
        fi
    else
        if [ "$UNDERVOLT_COUNT" -gt 0 ]; then
            log "✓ 电压恢复"
        fi
        UNDERVOLT_COUNT=0
        echo "OK" > "$STATUS_FILE"
    fi
    sleep "$CHECK_INTERVAL"
done

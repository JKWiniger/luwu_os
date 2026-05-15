#!/usr/bin/env python3
"""
XGO 手柄控制器
  读取 gamepad_config/mappings.json 中的按键映射，
  通过 evdev 监听手柄输入，调用 xgolib 实时控制机器人。

用法：
  python3 /home/luwu/XGO-Rider/gamepad_controller.py

依赖：pip install evdev xgolib
"""

import json
import os
import sys
import time
import signal
import threading
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [gamepad] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── 路径 ──────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(ROOT, "Luwu-OS", "libs", "gamepad_config", "mappings.json")

# ── 手柄识别 ──────────────────────────────────────────────────────
GAMEPAD_KEYWORDS = ["xbox", "microsoft", "wireless controller", "controller"]

# evdev 按键码 → 按钮索引（同 app.py 定义）
BUTTON_MAP = {
    304: 0,   # A
    305: 1,   # B
    306: 2,   # X
    307: 3,   # Y
    308: 4,   # LB
    309: 5,   # RB
    # index 6=LT / 7=RT：本控制器为纯模拟轴（ABS 2/5），无数字按键事件
    310: 8,   # Back
    311: 9,   # Start
    312: 10,  # L3
    313: 11,  # R3
    139: 16,  # Home (Xbox键)
}
# evdev ABS 码 → 轴索引
AXIS_MAP = {0: 0, 1: 1, 3: 2, 4: 3, 2: 4, 5: 5}

# ── 功能分类 ──────────────────────────────────────────────────────
# 按下立刻执行一次（不需要松开）
ONE_SHOT = {
    "stop",
    "action_1", "action_2", "action_3", "action_4", "action_5",
    "action_6", "action_7", "action_8", "action_9", "action_255",
    "rider_balance_on", "rider_balance_off",
    "rider_perform_on", "rider_perform_off",
    "rider_height_up", "rider_height_down",
    "imu_on", "imu_off",
    "perform_on", "perform_off",
    "pace_normal", "pace_slow", "pace_high",
    "gait_trot", "gait_walk",
    "claw_open", "claw_close",
    "height_up", "height_down",
    "arm_forward", "arm_back",
    "rumble_short", "rumble_long", "rumble_pulse",
}

# 持续按住时保持运动，松开归零
HOLD = {
    "rider_forward", "rider_back", "rider_turn_left", "rider_turn_right",
    "forward", "back", "left", "right", "turn_left", "turn_right",
}

# 轴映射（持续发送）
AXIS_FUNC = {
    "rider_axis_x", "rider_axis_yaw", "rider_roll_axis",
    "axis_x", "axis_y", "axis_yaw",
}


class XGOController:
    def __init__(self):
        self.xgo = None
        self.device_type = None   # "xgorider" / "xgomini" / "xgolite"
        self.mapping = {}         # {"button_0": "stop", "axis_1": "rider_axis_x", ...}
        self._held = set()        # 当前持续按住的按钮索引集合
        self._axes = {}           # {轴索引: 值}
        self._height = 90         # 当前车身高度（用于增减控制）
        self._running = False
        self._config_mtime = 0    # 配置文件最后修改时间
        self._gamepad_dev = None  # 当前手柄设备（用于震动）
        signal.signal(signal.SIGTERM, self._on_exit)
        signal.signal(signal.SIGINT, self._on_exit)

    # ── 初始化 ────────────────────────────────────────────────────

    def _init_xgo(self):
        try:
            import xgolib
            log.info("正在初始化 xgolib（自动识别设备）...")
            self.xgo = xgolib.XGO()
            fw = getattr(self.xgo, "version", "")
            if fw and fw[0] == "R":
                self.device_type = "xgorider"
            elif fw and fw[0] == "L":
                self.device_type = "xgolite"
            else:
                self.device_type = "xgomini"
            log.info(f"设备类型: {self.device_type}  固件: {fw}")
        except ImportError:
            log.warning("xgolib 未安装，仅输出日志（调试模式）")
        except Exception as e:
            log.error(f"xgolib 初始化失败: {e}")

    def _load_mapping(self):
        try:
            with open(CONFIG_FILE) as f:
                all_cfg = json.load(f)
            self.mapping = all_cfg.get(self.device_type or "xgorider", {})
            self._config_mtime = os.path.getmtime(CONFIG_FILE)
            log.info(f"已加载映射 ({self.device_type}): {len(self.mapping)} 项")
        except FileNotFoundError:
            self._config_mtime = 0
            log.warning(f"配置文件不存在: {CONFIG_FILE}，使用空映射")
        except Exception as e:
            log.error(f"读取配置失败: {e}")

    def _start_config_watcher(self):
        """后台线程：每2秒检测配置文件变更并热重载"""
        def _watch():
            while self._running:
                time.sleep(2)
                try:
                    mtime = os.path.getmtime(CONFIG_FILE)
                    if mtime != self._config_mtime:
                        log.info("检测到配置更新，热重载中...")
                        self._load_mapping()
                except Exception:
                    pass
        t = threading.Thread(target=_watch, daemon=True, name="config-watcher")
        t.start()

    def _find_gamepad(self):
        import evdev
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
                if any(kw in dev.name.lower() for kw in GAMEPAD_KEYWORDS):
                    log.info(f"找到手柄: {dev.name} ({path})")
                    return dev
            except Exception:
                pass
        return None

    # ── 震动反馈 ──────────────────────────────────────────────────

    def _rumble(self, strong=0x8000, weak=0x4000, duration_ms=250):
        """触发手柄震动反馈"""
        dev = self._gamepad_dev
        if not dev:
            return
        try:
            from evdev import ff, ecodes as ec
            rumble = ff.Rumble(strong_magnitude=strong, weak_magnitude=weak)
            effect = ff.Effect(
                ec.FF_RUMBLE, -1, 0,
                ff.Trigger(0, 0),
                ff.Replay(duration_ms, 0),
                ff.EffectType(ff_rumble_effect=rumble)
            )
            eid = dev.upload_effect(effect)
            dev.write(ec.EV_FF, eid, 1)
            threading.Timer(
                duration_ms / 1000 + 0.15,
                lambda: self._erase_effect(eid)
            ).start()
        except Exception as e:
            log.debug(f"震动失败: {e}")

    def _erase_effect(self, eid):
        try:
            if self._gamepad_dev:
                self._gamepad_dev.erase_effect(eid)
        except Exception:
            pass

    # ── xgolib 调用层 ─────────────────────────────────────────────

    def _call(self, func_id, axis_val=None):
        """根据 func_id 调用对应的 xgolib 方法"""
        if not func_id or func_id == "none":
            return

        xgo = self.xgo
        is_rider = (self.device_type == "xgorider")

        # ── 移动 ──
        if func_id == "stop":
            if xgo: xgo.stop()
            log.debug("stop")

        elif func_id == "rider_axis_x":
            v = (axis_val or 0) * 1.5
            if xgo: xgo.rider_move_x(v) if is_rider else xgo.move_x(v)
            log.debug(f"rider_axis_x {v:.2f}")

        elif func_id == "rider_axis_yaw":
            v = (axis_val or 0) * 360
            if xgo: xgo.rider_turn(v) if is_rider else xgo.turn(v)
            log.debug(f"rider_axis_yaw {v:.0f}")

        elif func_id == "rider_roll_axis":
            v = (axis_val or 0) * 17
            if xgo: xgo.rider_roll(v)
            log.debug(f"rider_roll {v:.2f}")

        elif func_id == "axis_x":
            v = -(axis_val or 0) * 25  # 向上推杆 → axis_val 负值 → 前进
            if xgo: xgo.move_x(v)
            log.debug(f"axis_x {v:.1f}")

        elif func_id == "axis_y":
            v = -(axis_val or 0) * 18
            if xgo: xgo.move_y(v)
            log.debug(f"axis_y {v:.1f}")

        elif func_id == "axis_yaw":
            v = -(axis_val or 0) * 100
            if xgo: xgo.turn(v)
            log.debug(f"axis_yaw {v:.1f}")

        # ── 持续按住移动 ──
        elif func_id == "rider_forward":
            if xgo: xgo.rider_move_x(1.5) if is_rider else xgo.move_x(25)
        elif func_id == "rider_back":
            if xgo: xgo.rider_move_x(-1.5) if is_rider else xgo.move_x(-25)
        elif func_id == "rider_turn_left":
            if xgo: xgo.rider_turn(90) if is_rider else xgo.turn(50)
        elif func_id == "rider_turn_right":
            if xgo: xgo.rider_turn(-90) if is_rider else xgo.turn(-50)

        elif func_id == "forward":
            if xgo: xgo.move_x(25)
        elif func_id == "back":
            if xgo: xgo.move_x(-25)
        elif func_id == "left":
            if xgo: xgo.move_y(18)
        elif func_id == "right":
            if xgo: xgo.move_y(-18)
        elif func_id == "turn_left":
            if xgo: xgo.turn(50)
        elif func_id == "turn_right":
            if xgo: xgo.turn(-50)

        # ── 高度控制（每次按键增减5） ──
        elif func_id in ("rider_height_up", "height_up"):
            self._height = min(self._height + 5, 120)
            if xgo:
                if is_rider: xgo.rider_height(self._height)
                else: xgo.translation("z", self._height)
            log.info(f"高度 → {self._height}")

        elif func_id in ("rider_height_down", "height_down"):
            self._height = max(self._height - 5, 60)
            if xgo:
                if is_rider: xgo.rider_height(self._height)
                else: xgo.translation("z", self._height)
            log.info(f"高度 → {self._height}")

        # ── 平衡 / IMU ──
        elif func_id == "rider_balance_on":
            if xgo: xgo.rider_balance_roll(1)
            log.info("横滚平衡 ON")
        elif func_id == "rider_balance_off":
            if xgo: xgo.rider_balance_roll(0)
            log.info("横滚平衡 OFF")
        elif func_id == "imu_on":
            if xgo: xgo.imu(1)
            log.info("自稳 ON")
        elif func_id == "imu_off":
            if xgo: xgo.imu(0)
            log.info("自稳 OFF")

        # ── 循环动作 ──
        elif func_id == "rider_perform_on":
            if xgo: xgo.rider_perform(1)
            log.info("循环动作 ON")
        elif func_id == "rider_perform_off":
            if xgo: xgo.rider_perform(0)
            log.info("循环动作 OFF")
        elif func_id == "perform_on":
            if xgo: xgo.perform(1)
            log.info("循环动作 ON")
        elif func_id == "perform_off":
            if xgo: xgo.perform(0)
            log.info("循环动作 OFF")

        # ── 步态 ──
        elif func_id == "pace_normal":
            if xgo: xgo.pace("normal")
        elif func_id == "pace_slow":
            if xgo: xgo.pace("slow")
        elif func_id == "pace_high":
            if xgo: xgo.pace("high")
        elif func_id == "gait_trot":
            if xgo: xgo.gait_type("trot")
        elif func_id == "gait_walk":
            if xgo: xgo.gait_type("walk")

        # ── 机械臂 ──
        elif func_id == "claw_open":
            if xgo: xgo.claw(255)
        elif func_id == "claw_close":
            if xgo: xgo.claw(0)
        elif func_id == "arm_forward":
            if xgo: xgo.arm(80, 60)
        elif func_id == "arm_back":
            if xgo: xgo.arm(-80, 60)

        # ── 震动 ──
        elif func_id == "rumble_short":
            self._rumble(0x8000, 0x4000, 150)
            log.debug("rumble short")
        elif func_id == "rumble_long":
            self._rumble(0xFFFF, 0x8000, 600)
            log.debug("rumble long")
        elif func_id == "rumble_pulse":
            self._rumble(0x5000, 0x3000, 80)
            log.debug("rumble pulse")

        # ── 动作 ──
        elif func_id.startswith("action_"):
            try:
                action_id = int(func_id.split("_")[1])
                if xgo:
                    if is_rider: xgo.rider_action(action_id)
                    else: xgo.action(action_id)
                log.info(f"action({action_id})")
                self._rumble(0xC000, 0x6000, 300)  # 动作执行时震动确认
            except (IndexError, ValueError):
                pass

        else:
            log.debug(f"未知功能 ID: {func_id}")

    def _stop_movement(self):
        """松开移动按键时归零"""
        if self.xgo:
            try:
                self.xgo.stop()
            except Exception:
                pass

    # ── 事件处理 ──────────────────────────────────────────────────

    def _on_button(self, btn_idx, pressed):
        key = f"button_{btn_idx}"
        func = self.mapping.get(key, "none")
        if func == "none":
            return

        if pressed:
            if func in ONE_SHOT:
                self._call(func)
            elif func in HOLD:
                self._held.add(btn_idx)
                self._call(func)
        else:
            if btn_idx in self._held:
                self._held.discard(btn_idx)
                # 如果没有其他移动按键还在按，则停止
                still_moving = any(
                    self.mapping.get(f"button_{i}", "none") in HOLD
                    for i in self._held
                )
                if not still_moving:
                    self._stop_movement()

    def _on_axis(self, axis_idx, value):
        self._axes[axis_idx] = value
        key = f"axis_{axis_idx}"
        func = self.mapping.get(key, "none")
        if func in AXIS_FUNC:
            DEADZONE = 0.12
            v = value if abs(value) > DEADZONE else 0.0
            if self.mapping.get(f"{key}_reversed", False):
                v = -v
            self._call(func, axis_val=v)

    # ── 主循环 ────────────────────────────────────────────────────

    def run(self):
        self._init_xgo()
        self._load_mapping()
        self._running = True
        self._start_config_watcher()

        import evdev
        while self._running:
            dev = self._find_gamepad()
            if not dev:
                log.warning("未找到手柄，2秒后重试...")
                time.sleep(2)
                continue

            log.info(f"开始监听: {dev.name}")
            self._gamepad_dev = dev
            try:
                abs_info = {code: dev.absinfo(code) for code in AXIS_MAP if hasattr(dev, "absinfo")}

                for event in dev.read_loop():
                    if not self._running:
                        break

                    if event.type == evdev.ecodes.EV_KEY:
                        idx = BUTTON_MAP.get(event.code)
                        if idx is not None:
                            self._on_button(idx, event.value == 1)

                    elif event.type == evdev.ecodes.EV_ABS:
                        code = event.code
                        if code in AXIS_MAP:
                            info = abs_info.get(code)
                            if info and info.max != info.min:
                                norm = (event.value - info.min) / (info.max - info.min) * 2 - 1
                                self._on_axis(AXIS_MAP[code], round(norm, 4))
                        elif code == 16:  # D-pad X
                            self._on_button(14, event.value == -1)
                            self._on_button(15, event.value == 1)
                            if event.value == 0:
                                self._on_button(14, False)
                                self._on_button(15, False)
                        elif code == 17:  # D-pad Y
                            self._on_button(12, event.value == -1)
                            self._on_button(13, event.value == 1)
                            if event.value == 0:
                                self._on_button(12, False)
                                self._on_button(13, False)

            except OSError:
                log.warning("手柄断开连接，等待重连...")
                self._gamepad_dev = None
                self._stop_movement()
                time.sleep(1)
            except Exception as e:
                log.error(f"事件循环异常: {e}")
                time.sleep(1)

    def _on_exit(self, *_):
        log.info("收到退出信号，停止机器人...")
        self._running = False
        self._stop_movement()
        sys.exit(0)


if __name__ == "__main__":
    log.info("XGO 手柄控制器启动")
    XGOController().run()

#!/usr/bin/env python3
"""
手柄配置 Web 服务 (evdev 版)
  Pi 端用 evdev 读取手柄，通过 WebSocket 实时推送到浏览器
  依赖: pip install flask flask-socketio evdev
  运行: python3 app.py  →  http://<Pi-IP>:5500
"""

import json
import os
import time
import threading
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "mappings.json")

# ── 手柄识别关键词 ─────────────────────────────────────────────────
GAMEPAD_KEYWORDS = ["xbox", "microsoft", "wireless controller", "gamepad", "controller", "tl_", "8bitdo", "ipega"]

# ── evdev → 标准按钮索引 (对齐浏览器 Gamepad API 标准布局) ───────────
# BTN_SOUTH=304(A) BTN_EAST=305(B) BTN_WEST=308(X) BTN_NORTH=307(Y)
# BTN_TL=310(LB) BTN_TR=311(RB) BTN_TL2=312(LT) BTN_TR2=313(RT)
# BTN_SELECT=314(Back) BTN_START=315(Start) BTN_THUMBL=317(L3) BTN_THUMBR=318(R3)
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

# evdev ABS 轴码 → 轴索引 (0=LX 1=LY 2=RX 3=RY 4=LT 5=RT)
AXIS_MAP = {0: 0, 1: 1, 3: 2, 4: 3, 2: 4, 5: 5}
# ABS_HAT0X=16 → 按钮 14(左)/15(右)
# ABS_HAT0Y=17 → 按钮 12(上)/13(下)

# ── 共享状态 ───────────────────────────────────────────────────────
_state = {
    "connected": False,
    "device": "",
    "buttons": [False] * 17,
    "axes": [0.0] * 6,
}
_lock = threading.Lock()
_last_emit = 0.0
EMIT_INTERVAL = 1 / 60  # 最高 60fps


def _snapshot():
    with _lock:
        return {
            "connected": _state["connected"],
            "device": _state["device"],
            "buttons": list(_state["buttons"]),
            "axes": list(_state["axes"]),
        }


def _emit_state(force=False):
    global _last_emit
    now = time.monotonic()
    if force or now - _last_emit >= EMIT_INTERVAL:
        _last_emit = now
        socketio.emit("gamepad_state", _snapshot())


# ── evdev 读取 ─────────────────────────────────────────────────────

def _find_gamepad():
    try:
        import evdev
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
                name = dev.name.lower()
                if any(kw in name for kw in GAMEPAD_KEYWORDS):
                    return dev
            except Exception:
                pass
    except ImportError:
        pass
    return None


def _norm(value, min_val, max_val):
    """归一化到 [-1, 1]"""
    if max_val == min_val:
        return 0.0
    return round((value - min_val) / (max_val - min_val) * 2.0 - 1.0, 4)


def _gamepad_reader():
    """后台线程：持续监听手柄事件"""
    while True:
        dev = _find_gamepad()
        if not dev:
            with _lock:
                if _state["connected"]:
                    _state.update(connected=False, device="",
                                  buttons=[False]*17, axes=[0.0]*6)
                    _emit_state(force=True)
            time.sleep(2)
            continue

        try:
            import evdev
            abs_info = {}
            for code in AXIS_MAP:
                try:
                    abs_info[code] = dev.absinfo(code)
                except Exception:
                    pass

            with _lock:
                _state["connected"] = True
                _state["device"] = dev.name
            _emit_state(force=True)

            for event in dev.read_loop():
                changed = False
                with _lock:
                    if event.type == evdev.ecodes.EV_KEY:
                        idx = BUTTON_MAP.get(event.code)
                        if idx is not None:
                            _state["buttons"][idx] = bool(event.value)
                            changed = True

                    elif event.type == evdev.ecodes.EV_ABS:
                        code = event.code
                        if code in AXIS_MAP:
                            info = abs_info.get(code)
                            if info:
                                val = _norm(event.value, info.min, info.max)
                                _state["axes"][AXIS_MAP[code]] = val
                                changed = True
                        elif code == 16:  # ABS_HAT0X (D-pad 左右)
                            _state["buttons"][14] = event.value == -1
                            _state["buttons"][15] = event.value == 1
                            changed = True
                        elif code == 17:  # ABS_HAT0Y (D-pad 上下)
                            _state["buttons"][12] = event.value == -1
                            _state["buttons"][13] = event.value == 1
                            changed = True

                if changed:
                    _emit_state()

        except Exception as e:
            print(f"[gamepad] 读取异常: {e}")
            with _lock:
                _state["connected"] = False
            _emit_state(force=True)
            time.sleep(1)


# ── 功能目录 & 默认映射 ──────────────────────────────────────────
# 每个 id 对应 gamepad_controller.py 中的执行逻辑
# axis: True 表示该功能应映射到摇杆/扳机轴，而非按键
FUNCTIONS = {
    # ── XGO-RIDER（两轮自平衡车）────────────────────────────────────
    # 无腿，不支持: 握手/挥手/翻滚/爬行/叫声/倒立/左右移
    # 专属 rider_* API + 通用 action()
    "xgorider": [
        {"id": "none",               "label": "── 不映射 ──",         "cat": ""},
        # 移动
        {"id": "stop",               "label": "停止",                 "cat": "移动"},
        {"id": "rider_axis_x",       "label": "前后速度 [轴]",         "cat": "移动", "axis": True},
        {"id": "rider_axis_yaw",     "label": "旋转速度 [轴]",         "cat": "移动", "axis": True},
        {"id": "rider_forward",      "label": "前进 (持续按住)",       "cat": "移动"},
        {"id": "rider_back",         "label": "后退 (持续按住)",       "cat": "移动"},
        {"id": "rider_turn_left",    "label": "左转 (持续按住)",       "cat": "移动"},
        {"id": "rider_turn_right",   "label": "右转 (持续按住)",       "cat": "移动"},
        # 车身姿态
        {"id": "rider_height_up",    "label": "升高车身",              "cat": "姿态"},
        {"id": "rider_height_down",  "label": "降低车身",              "cat": "姿态"},
        {"id": "rider_roll_axis",    "label": "车身横滚 [轴]",         "cat": "姿态", "axis": True},
        # 横滚平衡模式
        {"id": "rider_balance_on",   "label": "开启横滚平衡",          "cat": "平衡"},
        {"id": "rider_balance_off",  "label": "关闭横滚平衡",          "cat": "平衡"},
        # 动作（Rider 固件支持的 action ID）
        {"id": "action_1",           "label": "动作: 站立/平衡",       "cat": "动作"},
        {"id": "action_9",           "label": "动作: 舞蹈",            "cat": "动作"},
        {"id": "action_255",         "label": "动作: 重置",            "cat": "动作"},
        # 循环动作
        {"id": "rider_perform_on",   "label": "开启循环动作",          "cat": "系统"},
        {"id": "rider_perform_off",  "label": "关闭循环动作",          "cat": "系统"},
        # 震动
        {"id": "rumble_short",       "label": "震动: 短振 (150ms)",      "cat": "震动"},
        {"id": "rumble_long",        "label": "震动: 长振 (600ms)",      "cat": "震动"},
        {"id": "rumble_pulse",       "label": "震动: 轻振 (80ms)",       "cat": "震动"},
    ],
    # ── XGO-MINI（四足机器狗，带机械臂）────────────────────────────
    "xgomini": [
        {"id": "none",               "label": "── 不映射 ──",         "cat": ""},
        # 移动
        {"id": "stop",               "label": "停止",                 "cat": "移动"},
        {"id": "axis_x",             "label": "前后速度 [轴]",         "cat": "移动", "axis": True},
        {"id": "axis_y",             "label": "左右速度 [轴]",         "cat": "移动", "axis": True},
        {"id": "axis_yaw",           "label": "旋转速度 [轴]",         "cat": "移动", "axis": True},
        {"id": "forward",            "label": "前进 (持续按住)",       "cat": "移动"},
        {"id": "back",               "label": "后退 (持续按住)",       "cat": "移动"},
        {"id": "left",               "label": "左移 (持续按住)",       "cat": "移动"},
        {"id": "right",              "label": "右移 (持续按住)",       "cat": "移动"},
        {"id": "turn_left",          "label": "左转 (持续按住)",       "cat": "移动"},
        {"id": "turn_right",         "label": "右转 (持续按住)",       "cat": "移动"},
        # 姿态
        {"id": "height_up",          "label": "升高",                 "cat": "姿态"},
        {"id": "height_down",        "label": "降低",                 "cat": "姿态"},
        # 步态
        {"id": "pace_normal",        "label": "步态: 普通",            "cat": "步态"},
        {"id": "pace_slow",          "label": "步态: 慢速",            "cat": "步态"},
        {"id": "pace_high",          "label": "步态: 高频",            "cat": "步态"},
        {"id": "gait_trot",          "label": "步态: 小跑",            "cat": "步态"},
        {"id": "gait_walk",          "label": "步态: 行走",            "cat": "步态"},
        # 动作（四足狗 action ID 1-9 + 255 均支持）
        {"id": "action_1",           "label": "动作: 站立",            "cat": "动作"},
        {"id": "action_2",           "label": "动作: 坐下",            "cat": "动作"},
        {"id": "action_3",           "label": "动作: 握手",            "cat": "动作"},
        {"id": "action_4",           "label": "动作: 挥手",            "cat": "动作"},
        {"id": "action_5",           "label": "动作: 翻滚",            "cat": "动作"},
        {"id": "action_6",           "label": "动作: 爬行",            "cat": "动作"},
        {"id": "action_7",           "label": "动作: 叫声",            "cat": "动作"},
        {"id": "action_8",           "label": "动作: 倒立",            "cat": "动作"},
        {"id": "action_9",           "label": "动作: 舞蹈",            "cat": "动作"},
        {"id": "action_255",         "label": "动作: 重置",            "cat": "动作"},
        # 机械臂（MINI 标配机械臂）
        {"id": "claw_open",          "label": "爪子: 张开",            "cat": "机械臂"},
        {"id": "claw_close",         "label": "爪子: 合拢",            "cat": "机械臂"},
        {"id": "arm_forward",        "label": "机械臂: 前伸",          "cat": "机械臂"},
        {"id": "arm_back",           "label": "机械臂: 收回",          "cat": "机械臂"},
        # 系统
        {"id": "imu_on",             "label": "开启自稳",              "cat": "系统"},
        {"id": "imu_off",            "label": "关闭自稳",              "cat": "系统"},
        {"id": "perform_on",         "label": "开启循环动作",          "cat": "系统"},
        {"id": "perform_off",        "label": "关闭循环动作",          "cat": "系统"},
        # 震动
        {"id": "rumble_short",       "label": "震动: 短振 (150ms)",      "cat": "震动"},
        {"id": "rumble_long",        "label": "震动: 长振 (600ms)",      "cat": "震动"},
        {"id": "rumble_pulse",       "label": "震动: 轻振 (80ms)",       "cat": "震动"},
    ],
    # ── XGO-LITE（四足机器狗，同 MINI 方法集，无机械臂硬件）──────
    "xgolite": [
        {"id": "none",               "label": "── 不映射 ──",         "cat": ""},
        # 移动
        {"id": "stop",               "label": "停止",                 "cat": "移动"},
        {"id": "axis_x",             "label": "前后速度 [轴]",         "cat": "移动", "axis": True},
        {"id": "axis_y",             "label": "左右速度 [轴]",         "cat": "移动", "axis": True},
        {"id": "axis_yaw",           "label": "旋转速度 [轴]",         "cat": "移动", "axis": True},
        {"id": "forward",            "label": "前进 (持续按住)",       "cat": "移动"},
        {"id": "back",               "label": "后退 (持续按住)",       "cat": "移动"},
        {"id": "left",               "label": "左移 (持续按住)",       "cat": "移动"},
        {"id": "right",              "label": "右移 (持续按住)",       "cat": "移动"},
        {"id": "turn_left",          "label": "左转 (持续按住)",       "cat": "移动"},
        {"id": "turn_right",         "label": "右转 (持续按住)",       "cat": "移动"},
        # 姿态
        {"id": "height_up",          "label": "升高",                 "cat": "姿态"},
        {"id": "height_down",        "label": "降低",                 "cat": "姿态"},
        # 步态
        {"id": "pace_normal",        "label": "步态: 普通",            "cat": "步态"},
        {"id": "pace_slow",          "label": "步态: 慢速",            "cat": "步态"},
        {"id": "pace_high",          "label": "步态: 高频",            "cat": "步态"},
        {"id": "gait_trot",          "label": "步态: 小跑",            "cat": "步态"},
        {"id": "gait_walk",          "label": "步态: 行走",            "cat": "步态"},
        # 动作（LITE 四足动作 1-9 均支持，无机械臂相关动作）
        {"id": "action_1",           "label": "动作: 站立",            "cat": "动作"},
        {"id": "action_2",           "label": "动作: 坐下",            "cat": "动作"},
        {"id": "action_3",           "label": "动作: 握手",            "cat": "动作"},
        {"id": "action_4",           "label": "动作: 挥手",            "cat": "动作"},
        {"id": "action_5",           "label": "动作: 翻滚",            "cat": "动作"},
        {"id": "action_6",           "label": "动作: 爬行",            "cat": "动作"},
        {"id": "action_7",           "label": "动作: 叫声",            "cat": "动作"},
        {"id": "action_8",           "label": "动作: 倒立",            "cat": "动作"},
        {"id": "action_9",           "label": "动作: 舞蹈",            "cat": "动作"},
        {"id": "action_255",         "label": "动作: 重置",            "cat": "动作"},
        # 系统
        {"id": "imu_on",             "label": "开启自稳",              "cat": "系统"},
        {"id": "imu_off",            "label": "关闭自稳",              "cat": "系统"},
        {"id": "perform_on",         "label": "开启循环动作",          "cat": "系统"},
        {"id": "perform_off",        "label": "关闭循环动作",          "cat": "系统"},
        # 震动
        {"id": "rumble_short",       "label": "震动: 短振 (150ms)",      "cat": "震动"},
        {"id": "rumble_long",        "label": "震动: 长振 (600ms)",      "cat": "震动"},
        {"id": "rumble_pulse",       "label": "震动: 轻振 (80ms)",       "cat": "震动"},
    ],
}

DEFAULTS = {
    "xgorider": {
        # A=stop  B=action_1  X=action_255  Y=action_9
        "button_0": "stop", "button_1": "action_1", "button_2": "action_255",
        "button_3": "action_9",
        # LB=rider_balance_on  RB=rider_balance_off
        "button_4": "rider_balance_on", "button_5": "rider_balance_off",
        "button_6": "none", "button_7": "none",
        # Back=none  Start=action_255  L3=none  R3=none
        "button_8": "none", "button_9": "action_255",
        "button_10": "none", "button_11": "none",
        # D-Up=rider_height_up  D-Down=rider_height_down  D-Left=none  D-Right=none
        "button_12": "rider_height_up", "button_13": "rider_height_down",
        "button_14": "none", "button_15": "none",
        # Left Stick Y=前后  Right Stick X=旋转
        "axis_0": "none", "axis_1": "rider_axis_x",
        "axis_2": "rider_axis_yaw", "axis_3": "none",
        "axis_4": "none", "axis_5": "none",
    },
    "xgomini": {
        # A=stop  B=action_1  X=action_2  Y=action_9
        "button_0": "stop", "button_1": "action_1", "button_2": "action_2",
        "button_3": "action_9",
        # LB=action_3(握手)  RB=action_4(挥手)
        "button_4": "action_3", "button_5": "action_4",
        "button_6": "none", "button_7": "none",
        # Back=none  Start=action_255  L3=none  R3=none
        "button_8": "none", "button_9": "action_255",
        "button_10": "none", "button_11": "none",
        # D-Up=height_up  D-Down=height_down  D-Left=turn_left  D-Right=turn_right
        "button_12": "height_up", "button_13": "height_down",
        "button_14": "turn_left", "button_15": "turn_right",
        # Left Stick=前后/左右  Right Stick X=旋转
        "axis_0": "axis_y", "axis_1": "axis_x",
        "axis_2": "axis_yaw", "axis_3": "none",
        "axis_4": "none", "axis_5": "none",
    },
    "xgolite": {
        # A=stop  B=action_1  X=action_2  Y=action_9
        "button_0": "stop", "button_1": "action_1", "button_2": "action_2",
        "button_3": "action_9",
        # LB=imu_on  RB=imu_off
        "button_4": "imu_on", "button_5": "imu_off",
        "button_6": "none", "button_7": "none",
        "button_8": "none", "button_9": "action_255",
        "button_10": "none", "button_11": "none",
        "button_12": "height_up", "button_13": "height_down",
        "button_14": "turn_left", "button_15": "turn_right",
        "axis_0": "axis_y", "axis_1": "axis_x",
        "axis_2": "axis_yaw", "axis_3": "none",
        "axis_4": "none", "axis_5": "none",
    },
}


# ── REST 路由 ──────────────────────────────────────────────────────

def _load_all():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_all(data):
    os.makedirs(os.path.dirname(os.path.abspath(CONFIG_FILE)), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/devices")
def api_devices():
    return jsonify(list(DEFAULTS.keys()))


@app.route("/api/functions")
def api_functions():
    device = request.args.get("device", "xgorider")
    return jsonify(FUNCTIONS.get(device, FUNCTIONS["xgorider"]))


@app.route("/api/config", methods=["GET"])
def api_get_config():
    device = request.args.get("device", "xgorider")
    stored = _load_all()
    return jsonify(stored.get(device) or DEFAULTS.get(device, {}))


@app.route("/api/config", methods=["POST"])
def api_save_config():
    device = request.args.get("device", "xgorider")
    stored = _load_all()
    stored[device] = request.get_json()
    _save_all(stored)
    return jsonify({"ok": True})


@app.route("/api/reset", methods=["POST"])
def api_reset_config():
    device = request.args.get("device", "xgorider")
    stored = _load_all()
    stored.pop(device, None)
    _save_all(stored)
    return jsonify(DEFAULTS.get(device, {}))


# ── WebSocket ──────────────────────────────────────────────────────

@socketio.on("connect")
def on_ws_connect():
    emit("gamepad_state", _snapshot())  # 立即推送当前状态


# ── 启动 ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    t = threading.Thread(target=_gamepad_reader, daemon=True)
    t.start()
    print("手柄配置服务启动: http://0.0.0.0:5500")
    socketio.run(app, host="0.0.0.0", port=5500, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)

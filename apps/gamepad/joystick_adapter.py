#!/usr/bin/env python3
"""
Joystick → XGOController 适配层

将 2.4G 手柄的 /dev/input/js* 事件映射为 XGOController 的
button_X / axis_X 标准化索引，复用统一的键位映射配置体系。

映射规则：
  - joystick func code（如 0x0100=A 键）→ button_X 索引
  - joystick func code（如 0x0201=RK1_UP_DOWN）→ axis_X 索引
  - 映射配置使用 "joystick_<device_type>" 键（如 joystick_xgorider）
"""
import os
import sys
import time
import struct
import threading

# 确保能 import gamepad_controller
_GP_DIR = os.path.join(os.environ.get("LUWU_ROOT", "/opt/luwu-os"), "libs/gamepad_config")
if _GP_DIR not in sys.path:
    sys.path.insert(0, _GP_DIR)
import gamepad_controller as gc

# ── Joystick 物理按键/轴 → 标准化 button_X / axis_X 索引 ──────

# joystick func code → button index
JOYSTICK_BUTTON_MAP = {
    0x0100: 3,   # Y
    0x0101: 1,   # B
    0x0102: 0,   # A
    0x0103: 2,   # X
    0x0104: 4,   # L1
    0x0105: 5,   # R1
    0x0106: 6,   # L2
    0x0107: 7,   # R2
    0x0108: 8,   # SELECT
    0x0109: 9,   # START
    0x010A: 10,  # BTN_RK1
    0x010B: 11,  # BTN_RK2
}

# joystick func code → axis index
JOYSTICK_AXIS_MAP = {
    0x0200: 0,   # RK1_LR (左摇杆 左右)
    0x0201: 1,   # RK1_UD (左摇杆 上下)
    # 注意：右摇杆在此手柄上发送的是按钮事件（num=1/3，即 B/X 键），不是轴
    0x0203: 4,   # RK2_UD (右摇杆 上下)
}

# joystick button/axis 的可读名称（调试用）
JOYSTICK_BUTTON_NAMES = {
    0x0100: "Y",
    0x0101: "B",
    0x0102: "A",
    0x0103: "X",
    0x0104: "L1",
    0x0105: "R1",
    0x0106: "L2",
    0x0107: "R2",
    0x0108: "SELECT",
    0x0109: "START",
    0x010A: "BTN_RK1",
    0x010B: "BTN_RK2",
}

JOYSTICK_AXIS_NAMES = {
    0x0200: "RK1_LR",
    0x0201: "RK1_UD",
    # 0x0202: 此手柄右摇杆左右不发轴事件，见注释
    0x0203: "RK2_UD",
}


class JoystickReader:
    """读取 Linux /dev/input/js* 手柄设备

    使用 os.open / os.read / os.close（原生 fd）而非 Python 的 open("rb")。
    原因：BufferedReader 有内部锁，read() 阻塞在内核时持锁不释放，
    导致 stop() 中 close() 从 Qt 主线程调用时死锁等待，只能靠手柄发数据解困。
    os.read/os.close 没有内部锁，close 可以安全地从任意线程中断阻塞中的 read。
    """

    def __init__(self, js_id: int = 0):
        self._js_id = js_id
        self._jsdev: int = -1           # os.open 返回的原始 fd，-1 表示未连接
        self._connected = False
        self._running = False
        self._thread = None
        self._last_reconnect_attempt = 0.0

        # 缓存当前状态
        self.button_states: dict[int, int] = {}   # func_code → value (0/1)
        self.axis_states: dict[int, float] = {}    # func_code → normalized (-1..1)
        self._lock = threading.Lock()
        self._data_event = threading.Event()  # 有新数据时通知主循环

        self._try_open()

    def _try_open(self):
        js_path = f"/dev/input/js{self._js_id}"
        try:
            self._jsdev = os.open(js_path, os.O_RDONLY)
            self._connected = True
            print(f"[joystick_adapter] 手柄已连接: {js_path} (fd={self._jsdev})", flush=True)
        except Exception:
            self._connected = False
            self._jsdev = -1
            print(f"[joystick_adapter] 未找到手柄: {js_path}", flush=True)

    @property
    def connected(self) -> bool:
        return self._connected

    def start(self):
        if not self._connected:
            return
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """关闭 fd（可从任意线程安全调用，会立即中断 _read_loop 的 os.read 阻塞）"""
        self._running = False
        if self._jsdev >= 0:
            try:
                os.close(self._jsdev)
            except OSError:
                pass
            self._jsdev = -1
        self._connected = False

    def _read_loop(self):
        fd = self._jsdev
        while self._running and self._connected and fd >= 0:
            try:
                evbuf = os.read(fd, 8)
                if evbuf and len(evbuf) == 8:
                    t, value, etype, number = struct.unpack("IhBB", evbuf)
                    # 掩码去除 JS_EVENT_INIT (0x80) 标志
                    etype = etype & 0x7F
                    if etype not in (0x01, 0x02):
                        continue  # 跳过非按键/轴事件
                    func = (etype << 8) | number
                    with self._lock:
                        if func in JOYSTICK_BUTTON_MAP:
                            self.button_states[func] = value
                        elif func in JOYSTICK_AXIS_MAP:
                            self.axis_states[func] = value / 32767.0
                        else:
                            # 未映射事件 — 诊断右摇杆等未知按键/轴
                            print(f"[joystick] UNMAPPED event: func=0x{func:04X} type={etype} number={number} val={value}", flush=True)
                    self._data_event.set()  # 通知主循环有新数据
                elif evbuf:
                    # 读取不完整，丢弃
                    pass
            except BlockingIOError:
                time.sleep(0.01)
            except OSError as e:
                # EBADF=9: fd 已被 stop() 关闭，正常退出
                # ENODEV=19: 设备已移除
                print(f"[joystick_adapter] 读取错误 (errno={e.errno}): {e}", flush=True)
                self._connected = False
                break
            except Exception as e:
                print(f"[joystick_adapter] 读取异常: {e}", flush=True)
                self._connected = False
                break

    def try_reconnect(self):
        now = time.monotonic()
        if now - self._last_reconnect_attempt < 2.0:
            return
        self._last_reconnect_attempt = now
        if not self._connected:
            self._try_open()
            if self._connected:
                self.start()

    def get_states_snapshot(self):
        """线程安全地获取当前状态快照"""
        with self._lock:
            btns = dict(self.button_states)
            axes = dict(self.axis_states)
        return btns, axes


class JoystickController(gc.XGOController):
    """
    继承 XGOController，重写 run() 以支持 joystick 输入源。

    与 evdev 模式的区别：
      - 使用 JoystickReader 而非 evdev 读取输入
      - 映射配置使用 "joystick_<device_type>" 键
      - 步幅参数 (self._step_control) 影响轴速度缩放
    """

    def __init__(self, js_id: int = 0):
        super().__init__()
        self._js_id = js_id
        self._js_reader: JoystickReader | None = None

    # ── 重写：使用 joystick 专属映射键 ──────────────────────────

    def _load_mapping(self):
        """使用 joystick_<device_type> 映射键"""
        log = gc.log
        log.info(f">>> 加载 Joystick 配置文件: {self.CONFIG_FILE}")
        try:
            with open(self.CONFIG_FILE) as f:
                all_cfg = gc.json.load(f)
            log.info(f"  JSON 顶层 keys: {list(all_cfg.keys())}")
            # 优先用 joystick_<device_type>，fallback 到 <device_type>
            js_key = f"joystick_{self.device_type}"
            if js_key in all_cfg:
                self.mapping = all_cfg[js_key]
                log.info(f"  使用 joystick 专属映射: {js_key}")
            else:
                self.mapping = all_cfg.get(self.device_type or "xgorider", {})
                log.info(f"  使用通用映射: {self.device_type}")
            self._config_mtime = os.path.getmtime(self.CONFIG_FILE)
            log.info(f"  设备类型={self.device_type}, 映射项数={len(self.mapping)}")
            for k, v in self.mapping.items():
                if v != "none":
                    log.info(f"    {k} → {v}")
        except FileNotFoundError:
            self._config_mtime = 0
            log.warning(f"配置文件不存在: {self.CONFIG_FILE}，使用空映射")
        except Exception as e:
            log.error(f"读取配置失败: {e}")

    # ── 重写：joystick 主循环 ──────────────────────────────────

    def run(self):
        log = gc.log
        log.info("=" * 60)
        log.info("JoystickController.run() 启动 (2.4G 模式)")
        log.info(f"  CONFIG_FILE = {self.CONFIG_FILE}")
        log.info("=" * 60)

        # 仅在 xgo 未初始化时才初始化（允许外部预注入单例）
        # xgo=False 表示跳过机器人控制（debug/手柄映射测试模式）
        if self.xgo is None:
            self._init_xgo()
        if self.xgo is False:
            log.info("xgo=False，跳过机器人控制（纯手柄模式）")
        log.info(f"xgo 初始化完成: xgo={'✓' if self.xgo else '✗ None/False'}, "
                 f"device_type={self.device_type}")

        self._load_mapping()
        self._running = True
        self._start_config_watcher()

        # 启动 joystick 读取
        self._js_reader = JoystickReader(js_id=self._js_id)
        self._js_reader.start()

        # 主事件循环：Event.wait() 等待手柄数据，没数据时阻塞释放 GIL
        _prev_btns: dict[int, int] = {}
        _prev_axes: dict[int, float] = {}

        # 直接读取 launcher FIFO（绕过 Qt，确保 C 键永远可达）
        _keys_fd = getattr(self, '_keys_fifo_fd', -1)

        while self._running:
            if not self._js_reader.connected:
                self._js_reader.try_reconnect()
                time.sleep(0.5)
                continue

            # 等待手柄新数据（0.1s 超时用于快速响应 _running 变化）
            self._js_reader._data_event.wait(timeout=0.1)
            self._js_reader._data_event.clear()

            # ---- 检查 launcher 按键 FIFO（绕过 Qt）----
            if _keys_fd >= 0:
                try:
                    buf = os.read(_keys_fd, 32)
                    if buf:
                        for line in buf.decode().strip().split('\n'):
                            line = line.strip()
                            if not line:
                                continue
                            qt_key = int(line)
                            print(f"[joystick_adapter] FIFO key={qt_key} (0x{qt_key:x})", flush=True)
                            # Qt::Key_Back = 0x01000005 = C 键
                            if qt_key == 0x01000005:  # Key_Back (C键)
                                print("[joystick_adapter] C key via FIFO -> hard exit", flush=True)
                                self._running = False
                                os._exit(0)
                except BlockingIOError:
                    pass
                except Exception as e:
                    print(f"[joystick_adapter] FIFO read err: {e}", flush=True)

            btns, axes = self._js_reader.get_states_snapshot()

            # 处理按钮变化（边沿触发）
            for func_code, value in btns.items():
                prev = _prev_btns.get(func_code, 0)
                if value != prev:
                    _prev_btns[func_code] = value
                    btn_idx = JOYSTICK_BUTTON_MAP.get(func_code)
                    if btn_idx is not None:
                        self._on_button(btn_idx, value == 1)

            # 处理轴变化（阈值过滤 + 步幅缩放）
            for func_code, value in axes.items():
                prev = _prev_axes.get(func_code, 0.0)
                # 仅在变化超过死区时触发
                if abs(value - prev) > 0.03:
                    _prev_axes[func_code] = value
                    axis_idx = JOYSTICK_AXIS_MAP.get(func_code)
                    if axis_idx is not None:
                        # 步幅缩放：_step_control / 70 作为倍率
                        scaled = value * (self._step_control / 70.0)
                        # clamp 到 [-1, 1]
                        scaled = max(-1.0, min(1.0, scaled))
                        self._on_axis(axis_idx, round(scaled, 4))

        # 清理
        self._js_reader.stop()
        self._stop_movement()

    def _on_exit(self, *_):
        log = gc.log
        log.info("收到退出信号，停止机器人...")
        self._running = False
        self._stop_movement()
        if self._js_reader:
            self._js_reader.stop()
        sys.exit(0)


# ── 更新 CONFIG_FILE 引用（指向实际路径） ──
JoystickController.CONFIG_FILE = os.path.join(_GP_DIR, "mappings.json")

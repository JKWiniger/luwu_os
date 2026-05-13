# -*- coding: utf-8 -*-
"""Web 配置服务 - Flask + QR码 (PySide6 adapted)"""

import os
import json
import threading
import socket
import struct
import fcntl
import io
import qrcode
from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
DEFAULT_CONFIG_PATH = os.path.join(APP_DIR, "config_default.json")
FONT_PATH = os.path.join(APP_DIR, "msyh.ttc")
PORT = 5000


def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    elif os.path.exists(DEFAULT_CONFIG_PATH):
        with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(cfg):
    """保存配置文件"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)


def get_local_ip():
    """获取本机 IP"""
    for iface in ["wlan0", "eth0"]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ip = socket.inet_ntoa(fcntl.ioctl(
                s.fileno(), 0x8915,
                struct.pack("256s", bytes(iface[:15], "utf-8"))
            )[20:24])
            s.close()
            if ip and ip != "0.0.0.0":
                return ip
        except Exception:
            continue
    # Fallback
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_qr_image(url, size=120):
    """生成 QR 码 PIL Image"""
    qr = qrcode.QRCode(version=1, box_size=3, border=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    return qr_img.resize((size, size))


def is_config_complete(cfg=None):
    """检查 ASR / LLM / TTS / Role 是否都已配置"""
    if cfg is None:
        cfg = load_config()
    # ASR: 当前 provider 的 api_key 非空
    asr = cfg.get("asr", {})
    asr_provider = asr.get("provider", "aliyun")
    asr_key = asr.get(asr_provider, {}).get("api_key", "")
    if not asr_key:
        return False
    # LLM: api_key 和 base_url 非空
    llm = cfg.get("llm", {})
    if not llm.get("api_key", "") or not llm.get("base_url", ""):
        return False
    # TTS: 当前 provider 的 api_key 非空
    tts = cfg.get("tts", {})
    tts_provider = tts.get("provider", "aliyun")
    tts_key = tts.get(tts_provider, {}).get("api_key", "")
    if not tts_key:
        return False
    # Role: system_prompt 非空
    if not llm.get("system_prompt", ""):
        return False
    return True


class ConfigWebServer:
    """配置 Web 服务器"""

    def __init__(self, on_config_changed=None, on_generate_prompt=None):
        self.app = Flask(__name__)
        self.on_config_changed = on_config_changed
        self._on_generate_prompt = on_generate_prompt
        self._thread = None
        self._display_cb = None  # callback(pil_image) for PySide6 display
        self._setup_routes()

    def set_display_callback(self, callback):
        """Set callback for displaying images on PySide6 UI"""
        self._display_cb = callback

    def _setup_routes(self):
        from web_page import PAGE_HTML

        @self.app.route("/")
        def index():
            cfg = load_config()
            presets = cfg.get("llm", {}).get("presets", {})
            html = PAGE_HTML.replace("%%PRESETS%%", json.dumps(presets, ensure_ascii=False))
            html = html.replace("%%CONFIG%%", json.dumps(cfg, ensure_ascii=False))
            html = html.replace("%%LANGS%%", json.dumps({}, ensure_ascii=False))
            return html

        @self.app.route("/api/config", methods=["POST"])
        def save():
            try:
                cfg = request.get_json()
                save_config(cfg)
                if self.on_config_changed:
                    self.on_config_changed(cfg)
                # Refresh display
                if self._display_cb:
                    self._display_cb(self.generate_idle_image(show_start_button=True))
                return jsonify({"ok": True, "msg": "Configuration saved!"})
            except Exception as e:
                return jsonify({"ok": False, "msg": str(e)})

        @self.app.route("/api/test/asr", methods=["POST"])
        def test_asr():
            try:
                data = request.get_json()
                provider = data.get("provider", "aliyun")
                if provider == "aliyun":
                    key = data.get("aliyun", {}).get("api_key", "")
                    if not key:
                        return jsonify({"ok": False, "msg": "API Key is empty"})
                    return jsonify({"ok": True, "msg": f"Aliyun ASR config OK ({key[:8]}...)"})
                else:
                    key = data.get("deepgram", {}).get("api_key", "")
                    if not key:
                        return jsonify({"ok": False, "msg": "API Key is empty"})
                    import requests as req
                    resp = req.get("https://api.deepgram.com/v1/projects",
                                   headers={"Authorization": f"Token {key}"}, timeout=10)
                    if resp.status_code == 200:
                        return jsonify({"ok": True, "msg": "Deepgram API Key valid!"})
                    elif resp.status_code == 401:
                        return jsonify({"ok": False, "msg": "Invalid API Key (401)"})
                    else:
                        return jsonify({"ok": False, "msg": f"Deepgram API error (code={resp.status_code})"})
            except Exception as e:
                return jsonify({"ok": False, "msg": str(e)})

        @self.app.route("/api/test/llm", methods=["POST"])
        def test_llm():
            try:
                data = request.get_json()
                key = data.get("api_key", "")
                url = data.get("base_url", "")
                model = data.get("model", "")
                if not key or not url:
                    return jsonify({"ok": False, "msg": "API Key or Base URL is empty"})
                from openai import OpenAI
                client = OpenAI(api_key=key, base_url=url)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=100,
                    timeout=30
                )
                text = (resp.choices[0].message.content or "") if resp.choices else ""
                if not text:
                    return jsonify({"ok": True, "msg": "LLM OK! (connected)"})
                return jsonify({"ok": True, "msg": f"LLM OK! Response: {text[:30]}"})
            except Exception as e:
                error_msg = str(e)
                print(f"[WebServer] test_llm error: {error_msg[:200]}")
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    error_msg = "Connection timeout."
                elif "401" in error_msg or "unauthorized" in error_msg.lower():
                    error_msg = "Invalid API Key"
                elif "403" in error_msg or "forbidden" in error_msg.lower():
                    error_msg = "API Key forbidden"
                elif "429" in error_msg or "rate" in error_msg.lower():
                    error_msg = "Rate limited"
                return jsonify({"ok": False, "msg": error_msg[:300]})

        @self.app.route("/api/test/tts", methods=["POST"])
        def test_tts():
            try:
                data = request.get_json()
                provider = data.get("provider", "aliyun")
                if provider == "aliyun":
                    key = data.get("aliyun", {}).get("api_key", "")
                    if not key:
                        return jsonify({"ok": False, "msg": "API Key is empty"})
                    return jsonify({"ok": True, "msg": f"Aliyun TTS config OK ({key[:8]}...)"})
                else:
                    key = data.get("deepgram", {}).get("api_key", "")
                    if not key:
                        return jsonify({"ok": False, "msg": "API Key is empty"})
                    import requests as req
                    resp = req.get("https://api.deepgram.com/v1/projects",
                                   headers={"Authorization": f"Token {key}"}, timeout=10)
                    if resp.status_code == 200:
                        return jsonify({"ok": True, "msg": "Deepgram API Key valid!"})
                    elif resp.status_code == 401:
                        return jsonify({"ok": False, "msg": "Invalid API Key (401)"})
                    else:
                        return jsonify({"ok": False, "msg": f"Deepgram API error (code={resp.status_code})"})
            except Exception as e:
                return jsonify({"ok": False, "msg": str(e)})

        @self.app.route("/api/generate-prompt", methods=["POST"])
        def generate_prompt():
            try:
                data = request.get_json()
                requirements = data.get("requirements", "")
                agent_name = data.get("agent_name", "")
                user_nickname = data.get("user_nickname", "")
                if not requirements.strip():
                    return jsonify({"success": False, "error": "Requirements cannot be empty"})
                if self._on_generate_prompt:
                    result = self._on_generate_prompt(requirements, agent_name, user_nickname)
                    if isinstance(result, dict) and result.get("ok"):
                        return jsonify({"success": True, "prompt": result.get("prompt", "")})
                    else:
                        error_msg = result.get("error", "Generate failed") if isinstance(result, dict) else str(result)
                        return jsonify({"success": False, "error": error_msg})
                else:
                    return jsonify({"success": False, "error": "LLM not configured"})
            except Exception as e:
                return jsonify({"success": False, "error": str(e)})

        @self.app.route("/api/memory/clear", methods=["POST"])
        def clear_memory():
            try:
                cfg = load_config()
                if "memory" not in cfg:
                    cfg["memory"] = {}
                cfg["memory"]["content"] = ""
                save_config(cfg)
                if self.on_config_changed:
                    self.on_config_changed(cfg)
                return jsonify({"ok": True, "msg": "Memory cleared!"})
            except Exception as e:
                return jsonify({"ok": False, "msg": str(e)})

    def get_url(self):
        ip = get_local_ip()
        return f"http://{ip}:{PORT}"

    # ==================== Image generators for PySide6 ====================

    def generate_idle_image(self, show_start_button=False):
        """Generate idle state image (QR code + buttons) - returns PIL Image"""
        config_ready = is_config_complete() if show_start_button else False
        url = self.get_url()
        try:
            img = Image.new("RGB", (320, 240), (15, 21, 46))
            draw = ImageDraw.Draw(img)

            # Try loading font, fallback to default
            try:
                font_title = ImageFont.truetype(FONT_PATH, 18)
                font_text = ImageFont.truetype(FONT_PATH, 14)
                font_button = ImageFont.truetype(FONT_PATH, 16)
            except Exception:
                font_title = ImageFont.load_default()
                font_text = ImageFont.load_default()
                font_button = ImageFont.load_default()

            # QR code
            qr_img = generate_qr_image(url, size=120)
            qr_x = (320 - 120) // 2
            qr_y = 25
            img.paste(qr_img, (qr_x, qr_y))

            # Title
            draw.text((160, 6), "AI Chat", font=font_title, fill=(102, 178, 255), anchor="mt")

            # Hint text
            label_y = qr_y + 120 + 6
            draw.text((160, label_y), "Scan to configure",
                       font=font_text, fill=(200, 200, 200), anchor="mt")
            draw.text((160, label_y + 20), url,
                       font=font_text, fill=(128, 128, 128), anchor="mt")

            # Exit button (bottom-left)
            if show_start_button:
                exit_text = "Exit"
                try:
                    exit_text_width = draw.textlength(exit_text, font=font_button)
                except AttributeError:
                    exit_text_width = len(exit_text) * 12
                exit_btn_w = int(max(exit_text_width + 30, 100))
                exit_btn_h = 30
                exit_btn_x = 8
                exit_btn_y = 240 - exit_btn_h - 8
                draw.rounded_rectangle(
                    [(exit_btn_x, exit_btn_y), (exit_btn_x + exit_btn_w, exit_btn_y + exit_btn_h)],
                    radius=8,
                    fill=(102, 178, 255),
                    outline=(160, 210, 255),
                    width=2
                )
                draw.text(
                    (exit_btn_x + exit_btn_w // 2, exit_btn_y + exit_btn_h // 2),
                    exit_text,
                    font=font_button,
                    fill=(15, 21, 46),
                    anchor="mm"
                )

            # Start Chat button (bottom-right, only when config ready)
            if show_start_button and config_ready:
                btn_text = "Start Chat"
                try:
                    text_width = draw.textlength(btn_text, font=font_button)
                except AttributeError:
                    text_width = len(btn_text) * 12
                btn_width = int(max(text_width + 30, 100))
                btn_height = 30
                btn_x = 320 - btn_width - 8
                btn_y = 240 - btn_height - 8
                draw.rounded_rectangle(
                    [(btn_x, btn_y), (btn_x + btn_width, btn_y + btn_height)],
                    radius=8,
                    fill=(102, 178, 255),
                    outline=(160, 210, 255),
                    width=2
                )
                draw.text(
                    (btn_x + btn_width // 2, btn_y + btn_height // 2),
                    btn_text,
                    font=font_button,
                    fill=(15, 21, 46),
                    anchor="mm"
                )

            return img
        except Exception as e:
            print(f"[WebServer] generate_idle_image error: {e}")
            return Image.new("RGB", (320, 240), (15, 21, 46))

    def generate_status_image(self, text, color=(102, 178, 255)):
        """Generate a status text image - returns PIL Image"""
        try:
            img = Image.new("RGB", (320, 240), (15, 21, 46))
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype(FONT_PATH, 20)
            except Exception:
                font = ImageFont.load_default()
            draw.text((160, 120), text, font=font, fill=color, anchor="mm")
            return img
        except Exception as e:
            print(f"[WebServer] generate_status_image error: {e}")
            return Image.new("RGB", (320, 240), (15, 21, 46))

    def generate_listening_text_image(self, text):
        """Generate listening state image showing ASR partial text"""
        try:
            img = Image.new("RGB", (320, 240), (15, 21, 46))
            draw = ImageDraw.Draw(img)
            try:
                font_status = ImageFont.truetype(FONT_PATH, 16)
                font_text = ImageFont.truetype(FONT_PATH, 14)
            except Exception:
                font_status = ImageFont.load_default()
                font_text = ImageFont.load_default()

            # Status indicator
            draw.text((160, 22), "Listening...",
                      font=font_status, fill=(102, 178, 255), anchor="mm")
            draw.rectangle([(40, 40), (280, 42)], fill=(50, 60, 80))

            if text:
                lines = _wrap_text(text, font_text, max_width=280)
                y = 55
                for line in lines[-9:]:
                    draw.text((25, y), line, font=font_text, fill=(220, 220, 220))
                    y += 19
            else:
                draw.text((160, 130), "Speak now...",
                          font=font_text, fill=(130, 130, 130), anchor="mm")

            return img
        except Exception as e:
            print(f"[WebServer] generate_listening_text_image error: {e}")
            return Image.new("RGB", (320, 240), (15, 21, 46))

    # ==================== Server lifecycle ====================

    def start(self):
        """在后台线程启动 Flask"""
        import logging
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.WARNING)

        def _run():
            self.app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        print(f"[WebServer] Started at {self.get_url()}")

    def stop(self):
        """停止服务（daemon 线程会随主进程退出）"""
        pass


# ==================== Helper ====================

def _wrap_text(text, font, max_width=280):
    """简单文本换行（支持中英文混排）"""
    lines = []
    current_line = ""
    for char in text:
        try:
            bbox = font.getbbox(current_line + char)
            cur_width = bbox[2] - bbox[0]
        except Exception:
            cur_width = (len(current_line) + 1) * (14 if ord(char) > 127 else 8)
        if cur_width > max_width and current_line:
            lines.append(current_line)
            current_line = char
        else:
            current_line += char
    if current_line:
        lines.append(current_line)
    return lines

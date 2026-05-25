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

# ===== i18n =====
import sys as _sys
_LUWU_ROOT = os.environ.get("LUWU_ROOT", "/opt/luwu-os")
if _LUWU_ROOT not in _sys.path:
    _sys.path.insert(0, _LUWU_ROOT)
try:
    from libs.i18n import Translator as _Translator, get_lang as _get_lang
    _T = _Translator({
        "cn": {
            "idle_title": "AI 互动",
            "idle_scan": "请扫码或访问下方网址进行配置",
        },
        "en": {
            "idle_title": "AI Interactive",
            "idle_scan": "Scan QR or visit URL below to configure",
        },
    })
except Exception:
    _T = lambda k, *a: k
    _get_lang = lambda: "cn"

# ===== Web Page i18n (用于扫码后打开的 H5 配置页面) =====
_WEB_I18N = {
    "cn": {
        "PAGE_TITLE": "小陆同学",
        "TAB_ASR": "语音识别",
        "TAB_LLM": "AI 大脑",
        "TAB_TTS": "语音合成",
        "TAB_AGENT": "角色",
        "NAME_SECTION": "称呼设置",
        "AGENT_NAME_LABEL": "智能体名字",
        "AGENT_NAME_PLACEHOLDER": "如：小陆、XGO",
        "USER_NICKNAME_LABEL": "叫我什么",
        "USER_NICKNAME_PLACEHOLDER": "如：主人、小朋友",
        "PERSONALITY_TYPE": "选择您的性格类型",
        "QUICK_TEST": "快速测试",
        "QUIZ_Q1": "1. 和主人互动时，你更像...",
        "QUIZ_Q1_A": "热情话痨，主动找话题",
        "QUIZ_Q1_B": "安静陪伴，等主人开口",
        "QUIZ_Q2": "2. 在热闹的场合里，你会...",
        "QUIZ_Q2_A": "越聊越精神，享受人群",
        "QUIZ_Q2_B": "感到疲惫，想找个安静角落",
        "QUIZ_Q3": "3. 想表达观点时，你倾向...",
        "QUIZ_Q3_A": "边想边说，思路在交流中清晰",
        "QUIZ_Q3_B": "先在心里想清楚，再开口",
        "QUIZ_Q4": "4. 看待事物时，你更关注...",
        "QUIZ_Q4_A": "背后的含义和未来可能性",
        "QUIZ_Q4_B": "眼前的事实和具体细节",
        "QUIZ_Q5": "5. 回答问题时，你更倾向...",
        "QUIZ_Q5_A": "讲故事、举例子、用比喻",
        "QUIZ_Q5_B": "给知识、讲道理、列要点",
        "QUIZ_Q6": "6. 学习新东西，你喜欢...",
        "QUIZ_Q6_A": "先理解概念，再去用",
        "QUIZ_Q6_B": "先动手做，边做边学",
        "QUIZ_Q7": "7. 主人遇到困难时，你会...",
        "QUIZ_Q7_A": "温暖鼓励，给情感支持",
        "QUIZ_Q7_B": "冷静分析，给解决方案",
        "QUIZ_Q8": "8. 判断一件事，你更看重...",
        "QUIZ_Q8_A": "对方的感受是否被照顾到",
        "QUIZ_Q8_B": "逻辑是否成立、是非对错",
        "QUIZ_Q9": "9. 你的说话风格是...",
        "QUIZ_Q9_A": "活泼跳跃，爱开玩笑",
        "QUIZ_Q9_B": "沉稳有序，条理清晰",
        "QUIZ_Q10": "10. 面对计划，你更倾向...",
        "QUIZ_Q10_A": "保持灵活，随机应变",
        "QUIZ_Q10_B": "提前安排好，按部就班",
        "REQUIREMENTS": "对机器人的具体要求",
        "REQUIREMENTS_PLACEHOLDER": "写下你希望机器人具备的性格、说话风格或行为习惯，例如：活泼开朗、爱讲冷笑话、说话简洁、对新事物充满好奇...",
        "GENERATE_EDIT_SECTION": "生成与编辑",
        "GENERATE_PROMPT": "✨ 自动生成提示词",
        "CURRENT_PROMPT": "当前提示词",
        "PROMPT_HINT": "此提示词将作为 LLM 的 System Prompt",
        "MEMORY_SECTION": "长期记忆",
        "MEMORY_ENABLE": "启用长期记忆",
        "MEMORY_TIP": "开启后，每次对话结束时会自动总结并记住用户偏好、习惯等信息，下次对话时会自动带入",
        "MEMORY_PLACEHOLDER": "记忆内容会在对话后自动更新...",
        "MEMORY_CLEAR_BTN": "清除记忆",
        "MEMORY_CHAR_COUNT": "字",
        "MEMORY_CONFIRM": "确定要清除所有长期记忆吗？此操作不可撤销。",
        "MEMORY_CLEARED": "记忆已清除",
        "ASR_PROVIDER_LABEL": "Provider",
        "ASR_API_KEY_LABEL": "API Key",
        "ASR_API_KEY_PLACEHOLDER": "sk-xxx",
        "ASR_MODEL_LABEL": "Model",
        "ASR_LANGUAGE_LABEL": "Language",
        "ASR_VAD_LABEL": "VAD Threshold",
        "ASR_SILENCE_LABEL": "Silence (ms)",
        "ASR_DG_KEY_PLACEHOLDER": "Your Deepgram API Key",
        "ASR_VAD_SILENCE_LABEL": "VAD Silence (ms)",
        "ASR_DG_TIP": "Deepgram ASR: Real-time WebSocket streaming with built-in VAD. Get API key at deepgram.com",
        "ASR_TEST_BTN": "Test ASR Connection",
        "ASR_LANG_ZH": "中文",
        "ASR_LANG_EN": "English",
        "ASR_PROVIDER_ALIYUN": "阿里云 千问 Aliyun Qwen (China)",
        "ASR_PROVIDER_DEEPGRAM": "Deepgram (Global, Real-time VAD)",
        "LLM_PROVIDER_LABEL": "Provider Preset",
        "LLM_API_KEY_LABEL": "API Key",
        "LLM_API_KEY_PLACEHOLDER": "sk-xxx",
        "LLM_BASE_URL_LABEL": "Base URL (OpenAI Compatible)",
        "LLM_MODEL_LABEL": "Model",
        "LLM_MODEL_PLACEHOLDER": "model-id",
        "PROMPT_MOVED_HINT": "💡 系统提示词请在「角色」标签页配置",
        "LLM_TOOLS_LABEL": "Enable Function Call (Robot Control)",
        "LLM_SEARCH_LABEL": "Enable Web Search",
        "LLM_VLM_TIP": "📷 VLM (Vision): To enable photo recognition, select a vision-capable model above (e.g. qwen3.6-plus, gpt-5.5, gemini-3.1-pro-preview). No separate VLM config needed.",
        "LLM_TEST_BTN": "Test LLM Connection",
        "LLM_PROVIDER_ALIYUN": "阿里云通义 / Alibaba Qwen",
        "LLM_PROVIDER_OPENAI": "OpenAI",
        "LLM_PROVIDER_GOOGLE": "Google Gemini",
        "LLM_PROVIDER_DOUBAO": "字节豆包 / Doubao",
        "LLM_PROVIDER_CUSTOM": "Custom / 自定义",
        "LLM_TESTING": "Testing... (may take 10-30s for Google Gemini)",
        "LLM_EMPTY_RESPONSE": "Empty response from server. Check server logs.",
        "LLM_INVALID_RESPONSE": "Invalid response",
        "LLM_REQUEST_TIMEOUT": "Request timeout. Check network or API Key.",
        "TTS_PROVIDER_LABEL": "Provider",
        "TTS_API_KEY_LABEL": "API Key",
        "TTS_ALIYUN_KEY_PLACEHOLDER": "sk-xxx (same as ASR if Aliyun)",
        "TTS_VOICE_LABEL": "Voice",
        "TTS_DG_KEY_PLACEHOLDER": "Your Deepgram API Key",
        "TTS_MODEL_LABEL": "Model / Voice",
        "TTS_SAMPLE_RATE_LABEL": "Sample Rate",
        "TTS_DG_TIP": "Deepgram TTS: Real-time WebSocket streaming synthesis. Get API key at deepgram.com",
        "TTS_TEST_BTN": "Test TTS",
        "TTS_PROVIDER_ALIYUN": "阿里云 千问 Aliyun Qwen (China)",
        "TTS_PROVIDER_DEEPGRAM": "Deepgram (Global, Real-time Streaming)",
        "SAVE_BTN": "💾 Save Configuration",
        "SAVE_SUCCESS": "配置已保存！",
        "SAVE_ERROR": "保存失败",
        "NETWORK_ERROR": "网络错误",
        "TESTING": "测试中...",
        "GENERATING": "生成中...",
        "GENERATE_FAIL": "生成失败",
        "GENERATE_NET_ERROR": "网络错误",
        "DEFAULT_SYSTEM_PROMPT": "你是XGO机器人助手。回答要简洁。",
        "MBTI_DESC_TEMPLATE": "我的 MBTI 是 {code}（{name}）。",
        "MBTI_INTJ": "建筑师",
        "MBTI_INTP": "逻辑学家",
        "MBTI_ENTJ": "指挥官",
        "MBTI_ENTP": "辩论家",
        "MBTI_INFJ": "提倡者",
        "MBTI_INFP": "调停者",
        "MBTI_ENFJ": "主人公",
        "MBTI_ENFP": "竞选者",
        "MBTI_ISTJ": "物流师",
        "MBTI_ISFJ": "守护者",
        "MBTI_ESTJ": "总经理",
        "MBTI_ESFJ": "执政官",
        "MBTI_ISTP": "鉴赏家",
        "MBTI_ISFP": "探险家",
        "MBTI_ESTP": "企业家",
        "MBTI_ESFP": "表演者",
    },
    "en": {
        "PAGE_TITLE": "XGO Buddy",
        "TAB_ASR": "Speech",
        "TAB_LLM": "AI Brain",
        "TAB_TTS": "Voice",
        "TAB_AGENT": "Agent",
        "NAME_SECTION": "Naming",
        "AGENT_NAME_LABEL": "Agent Name",
        "AGENT_NAME_PLACEHOLDER": "e.g. XGO, Buddy",
        "USER_NICKNAME_LABEL": "Call Me",
        "USER_NICKNAME_PLACEHOLDER": "e.g. Master, Friend",
        "PERSONALITY_TYPE": "Choose Personality Type",
        "QUICK_TEST": "Quick Test",
        "QUIZ_Q1": "1. When interacting, you are more like...",
        "QUIZ_Q1_A": "Enthusiastic, actively starts conversations",
        "QUIZ_Q1_B": "Quiet companion, waits for others to speak",
        "QUIZ_Q2": "2. In lively social settings, you...",
        "QUIZ_Q2_A": "Get more energized, enjoy the crowd",
        "QUIZ_Q2_B": "Feel drained, look for a quiet corner",
        "QUIZ_Q3": "3. When expressing ideas, you tend to...",
        "QUIZ_Q3_A": "Think out loud, ideas clarify through talking",
        "QUIZ_Q3_B": "Think internally first, then speak",
        "QUIZ_Q4": "4. When looking at things, you focus more on...",
        "QUIZ_Q4_A": "Underlying meaning and future possibilities",
        "QUIZ_Q4_B": "Present facts and concrete details",
        "QUIZ_Q5": "5. When answering questions, you prefer...",
        "QUIZ_Q5_A": "Telling stories with examples and metaphors",
        "QUIZ_Q5_B": "Giving facts, reasoning, listing key points",
        "QUIZ_Q6": "6. When learning new things, you like to...",
        "QUIZ_Q6_A": "Understand the concept first, then apply",
        "QUIZ_Q6_B": "Start hands-on, learn by doing",
        "QUIZ_Q7": "7. When someone faces a problem, you...",
        "QUIZ_Q7_A": "Offer warm encouragement and emotional support",
        "QUIZ_Q7_B": "Analyze calmly and provide solutions",
        "QUIZ_Q8": "8. When judging something, you value...",
        "QUIZ_Q8_A": "Whether people's feelings are taken care of",
        "QUIZ_Q8_B": "Whether logic holds and if it's right or wrong",
        "QUIZ_Q9": "9. Your speaking style is more...",
        "QUIZ_Q9_A": "Playful and spontaneous, love jokes",
        "QUIZ_Q9_B": "Steady and structured, clear and orderly",
        "QUIZ_Q10": "10. When it comes to plans, you prefer...",
        "QUIZ_Q10_A": "Staying flexible, adapt on the fly",
        "QUIZ_Q10_B": "Planning ahead and following through",
        "REQUIREMENTS": "Specific Requirements for the Robot",
        "REQUIREMENTS_PLACEHOLDER": "Describe the personality, speaking style, or behavior you want the robot to have, e.g.: cheerful and outgoing, loves telling jokes, speaks concisely, curious about new things...",
        "GENERATE_EDIT_SECTION": "Generate & Edit",
        "GENERATE_PROMPT": "✨ Auto Generate Prompt",
        "CURRENT_PROMPT": "Current Prompt",
        "PROMPT_HINT": "This prompt will be used as the LLM System Prompt",
        "MEMORY_SECTION": "Long-term Memory",
        "MEMORY_ENABLE": "Enable Long-term Memory",
        "MEMORY_TIP": "When enabled, user preferences and habits are automatically summarized after each conversation and recalled in future sessions.",
        "MEMORY_PLACEHOLDER": "Memory will auto-update after conversations...",
        "MEMORY_CLEAR_BTN": "Clear Memory",
        "MEMORY_CHAR_COUNT": "chars",
        "MEMORY_CONFIRM": "Are you sure you want to clear all long-term memory? This cannot be undone.",
        "MEMORY_CLEARED": "Memory cleared",
        "ASR_PROVIDER_LABEL": "Provider",
        "ASR_API_KEY_LABEL": "API Key",
        "ASR_API_KEY_PLACEHOLDER": "sk-xxx",
        "ASR_MODEL_LABEL": "Model",
        "ASR_LANGUAGE_LABEL": "Language",
        "ASR_VAD_LABEL": "VAD Threshold",
        "ASR_SILENCE_LABEL": "Silence (ms)",
        "ASR_DG_KEY_PLACEHOLDER": "Your Deepgram API Key",
        "ASR_VAD_SILENCE_LABEL": "VAD Silence (ms)",
        "ASR_DG_TIP": "Deepgram ASR: Real-time WebSocket streaming with built-in VAD. Get API key at deepgram.com",
        "ASR_TEST_BTN": "Test ASR Connection",
        "ASR_LANG_ZH": "Chinese",
        "ASR_LANG_EN": "English",
        "ASR_PROVIDER_ALIYUN": "Aliyun Qwen (China)",
        "ASR_PROVIDER_DEEPGRAM": "Deepgram (Global, Real-time VAD)",
        "LLM_PROVIDER_LABEL": "Provider Preset",
        "LLM_API_KEY_LABEL": "API Key",
        "LLM_API_KEY_PLACEHOLDER": "sk-xxx",
        "LLM_BASE_URL_LABEL": "Base URL (OpenAI Compatible)",
        "LLM_MODEL_LABEL": "Model",
        "LLM_MODEL_PLACEHOLDER": "model-id",
        "PROMPT_MOVED_HINT": "💡 System prompt is configured in the Agent tab",
        "LLM_TOOLS_LABEL": "Enable Function Call (Robot Control)",
        "LLM_SEARCH_LABEL": "Enable Web Search",
        "LLM_VLM_TIP": "📷 VLM (Vision): To enable photo recognition, select a vision-capable model above (e.g. qwen3.6-plus, gpt-5.5, gemini-3.1-pro-preview). No separate VLM config needed.",
        "LLM_TEST_BTN": "Test LLM Connection",
        "LLM_PROVIDER_ALIYUN": "Alibaba Qwen",
        "LLM_PROVIDER_OPENAI": "OpenAI",
        "LLM_PROVIDER_GOOGLE": "Google Gemini",
        "LLM_PROVIDER_DOUBAO": "ByteDance Doubao",
        "LLM_PROVIDER_CUSTOM": "Custom",
        "LLM_TESTING": "Testing... (may take 10-30s for Google Gemini)",
        "LLM_EMPTY_RESPONSE": "Empty response from server. Check server logs.",
        "LLM_INVALID_RESPONSE": "Invalid response",
        "LLM_REQUEST_TIMEOUT": "Request timeout. Check network or API Key.",
        "TTS_PROVIDER_LABEL": "Provider",
        "TTS_API_KEY_LABEL": "API Key",
        "TTS_ALIYUN_KEY_PLACEHOLDER": "sk-xxx (same as ASR if Aliyun)",
        "TTS_VOICE_LABEL": "Voice",
        "TTS_DG_KEY_PLACEHOLDER": "Your Deepgram API Key",
        "TTS_MODEL_LABEL": "Model / Voice",
        "TTS_SAMPLE_RATE_LABEL": "Sample Rate",
        "TTS_DG_TIP": "Deepgram TTS: Real-time WebSocket streaming synthesis. Get API key at deepgram.com",
        "TTS_TEST_BTN": "Test TTS",
        "TTS_PROVIDER_ALIYUN": "Aliyun Qwen (China)",
        "TTS_PROVIDER_DEEPGRAM": "Deepgram (Global, Real-time Streaming)",
        "SAVE_BTN": "💾 Save Configuration",
        "SAVE_SUCCESS": "Configuration saved!",
        "SAVE_ERROR": "Save failed",
        "NETWORK_ERROR": "Network error",
        "TESTING": "Testing...",
        "GENERATING": "Generating...",
        "GENERATE_FAIL": "Generation failed",
        "GENERATE_NET_ERROR": "Network error",
        "DEFAULT_SYSTEM_PROMPT": "You are XGO robot assistant. Keep responses concise.",
        "MBTI_DESC_TEMPLATE": "My MBTI is {code} ({name}).",
        "MBTI_INTJ": "Architect",
        "MBTI_INTP": "Logician",
        "MBTI_ENTJ": "Commander",
        "MBTI_ENTP": "Debater",
        "MBTI_INFJ": "Advocate",
        "MBTI_INFP": "Mediator",
        "MBTI_ENFJ": "Protagonist",
        "MBTI_ENFP": "Campaigner",
        "MBTI_ISTJ": "Logistician",
        "MBTI_ISFJ": "Defender",
        "MBTI_ESTJ": "Executive",
        "MBTI_ESFJ": "Consul",
        "MBTI_ISTP": "Virtuoso",
        "MBTI_ISFP": "Adventurer",
        "MBTI_ESTP": "Entrepreneur",
        "MBTI_ESFP": "Entertainer",
    },
}

def _get_web_langs():
    """返回当前语言对应的 Web 页面翻译字典"""
    try:
        lang = _get_lang()
        return _WEB_I18N.get(lang, _WEB_I18N.get("cn", {}))
    except Exception:
        return {}

# 全屏背景底图（与启动页一致）
_APP_BG_IMAGE_PATH = os.path.join(os.environ.get("LUWU_ROOT", "/opt/luwu-os"), "assets/images/app_bg.png")
_APP_BG_PIL = None
try:
    if os.path.exists(_APP_BG_IMAGE_PATH):
        _APP_BG_PIL = Image.open(_APP_BG_IMAGE_PATH).convert("RGB").resize((320, 240))
except Exception as _e:
    print(f"[WebServer] bg image load error: {_e}")


def _new_canvas():
    """返回一份启动页背景的副本，背景图缺失时回落原深色。"""
    if _APP_BG_PIL is not None:
        return _APP_BG_PIL.copy()
    return Image.new("RGB", (320, 240), (15, 21, 46))


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


def _sync_aliyun_key(cfg):
    """统一阿里云 api_key：从 ASR/LLM/TTS 三处中取第一个非空的 aliyun key，
    回填到其他空缺位置，避免用户在多个 tab 重复输入。"""
    try:
        asr = cfg.setdefault("asr", {})
        llm = cfg.setdefault("llm", {})
        tts = cfg.setdefault("tts", {})
        asr_aliyun = asr.setdefault("aliyun", {})
        tts_aliyun = tts.setdefault("aliyun", {})
        provider_keys = llm.setdefault("provider_keys", {})

        # 收集候选 key（按优先级：用户最近交互通常 LLM 主键 > 各 provider 副本）
        llm_aliyun_key = ""
        if llm.get("provider") == "aliyun":
            llm_aliyun_key = llm.get("api_key", "") or ""
        if not llm_aliyun_key:
            llm_aliyun_key = provider_keys.get("aliyun", "") or ""

        candidates = [
            asr_aliyun.get("api_key", "") or "",
            llm_aliyun_key,
            tts_aliyun.get("api_key", "") or "",
        ]
        unified = next((k for k in candidates if k), "")
        if not unified:
            return cfg

        if not asr_aliyun.get("api_key"):
            asr_aliyun["api_key"] = unified
        if not tts_aliyun.get("api_key"):
            tts_aliyun["api_key"] = unified
        if not provider_keys.get("aliyun"):
            provider_keys["aliyun"] = unified
        if llm.get("provider") == "aliyun" and not llm.get("api_key"):
            llm["api_key"] = unified
    except Exception as e:
        print(f"[WebServer] _sync_aliyun_key error: {e}")
    return cfg


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
            html = html.replace("%%LANGS%%", json.dumps(_get_web_langs(), ensure_ascii=False))
            return html

        @self.app.route("/api/config", methods=["POST"])
        def save():
            try:
                cfg = request.get_json()
                # 统一 aliyun api_key：一处填写、三处共享
                _sync_aliyun_key(cfg)
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
                user_personality = data.get("user_personality", "")
                if not requirements.strip():
                    return jsonify({"success": False, "error": "Requirements cannot be empty"})
                if self._on_generate_prompt:
                    result = self._on_generate_prompt(requirements, agent_name, user_nickname, user_personality)
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
            img = _new_canvas()
            draw = ImageDraw.Draw(img)

            # Try loading font, fallback to default
            try:
                font_title = ImageFont.truetype(FONT_PATH, 18)
                font_text = ImageFont.truetype(FONT_PATH, 14)
            except Exception:
                font_title = ImageFont.load_default()
                font_text = ImageFont.load_default()

            # QR code
            qr_img = generate_qr_image(url, size=120)
            qr_x = (320 - 120) // 2
            qr_y = 25
            img.paste(qr_img, (qr_x, qr_y))

            # Title（深蓝，适应浅色背景）
            draw.text((160, 6), _T("idle_title"), font=font_title, fill=(30, 64, 175), anchor="mt")

            # Hint text（深色文字）
            label_y = qr_y + 120 + 6
            draw.text((160, label_y), _T("idle_scan"),
                       font=font_text, fill=(40, 50, 80), anchor="mt")
            draw.text((160, label_y + 20), url,
                       font=font_text, fill=(80, 90, 120), anchor="mt")

            # Bottom hint removed (idle_web text no longer needed)

            return img
        except Exception as e:
            print(f"[WebServer] generate_idle_image error: {e}")
            return _new_canvas()

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

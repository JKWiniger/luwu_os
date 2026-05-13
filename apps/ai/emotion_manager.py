# -*- coding: utf-8 -*-
"""Emotion Manager - sentiment keyword matching + expression animation (PySide6 adapted)"""

import os
import time
import threading
import glob
from PIL import Image

APP_DIR = os.path.dirname(os.path.abspath(__file__))
EXPRESSION_BASE = os.path.join(APP_DIR, "expression")
EXPRESSION_DOG_LM = os.path.join(EXPRESSION_BASE, "dog_LM")

# Emotion keyword mapping: keyword list -> expression directory name
EMOTION_MAP = {
    "happy": {
        "dir": "happy",
        "keywords_cn": ["开心", "哈哈", "太好了", "棒", "好的", "没问题", "当然",
                         "乐意", "成功", "完成", "恭喜", "欢迎", "好呀"],
        "keywords_en": ["happy", "great", "wonderful", "nice", "good", "sure",
                         "awesome", "excellent", "perfect", "congratulations"]
    },
    "sad": {
        "dir": "sad",
        "keywords_cn": ["难过", "抱歉", "对不起", "遗憾", "可惜", "不好意思",
                         "失败", "做不到", "无法"],
        "keywords_en": ["sorry", "sad", "unfortunately", "cannot", "failed",
                         "impossible", "regret"]
    },
    "surprise": {
        "dir": "surprise",
        "keywords_cn": ["哇", "真的吗", "厉害", "惊讶", "天哪", "居然", "没想到",
                         "不可思议"],
        "keywords_en": ["wow", "really", "amazing", "incredible", "unbelievable",
                         "surprising"]
    },
    "shy": {
        "dir": "shy",
        "keywords_cn": ["谢谢", "害羞", "不好意思", "过奖", "夸奖", "客气"],
        "keywords_en": ["thank", "blush", "flattered", "kind"]
    },
    "query": {
        "dir": "query",
        "keywords_cn": ["让我想想", "思考", "嗯", "这个问题", "我想一下", "分析"],
        "keywords_en": ["think", "hmm", "let me", "consider", "analyze"]
    },
    "angry": {
        "dir": "angry",
        "keywords_cn": ["生气", "不对", "错误", "不行", "不可以", "警告"],
        "keywords_en": ["angry", "wrong", "error", "no", "stop", "warning"]
    },
    "love": {
        "dir": "love",
        "keywords_cn": ["喜欢", "爱", "最好的", "宝贝"],
        "keywords_en": ["love", "like", "favorite", "best"]
    },
    "naughty": {
        "dir": "naughty",
        "keywords_cn": ["嘿嘿", "调皮", "逗你", "开玩笑", "哼"],
        "keywords_en": ["hehe", "joking", "tease", "playful"]
    },
}

# Emotion number prefix mapping (LLM outputs 1-8 as first char)
EMOTION_NUM_MAP = {
    "1": "happy",
    "2": "sad",
    "3": "surprise",
    "4": "shy",
    "5": "query",
    "6": "angry",
    "7": "love",
    "8": "naughty",
}

# Default expression when no emotion matched
DEFAULT_EMOTION = "eyes"


class EmotionManager:
    """Emotion analysis + expression animation playback (PySide6)"""

    def __init__(self, display_callback=None):
        """
        display_callback: function(pil_image) called to display each frame on UI.
        Should convert PIL Image -> QPixmap and set on a QLabel.
        If None, expressions are skipped silently.
        """
        self._display_cb = display_callback
        self._animation_thread = None
        self._stop_animation = False
        self._frame_cache = {}

        # Check which expression dirs exist
        base = EXPRESSION_DOG_LM if os.path.isdir(EXPRESSION_DOG_LM) else EXPRESSION_BASE
        self.expression_base = base
        self.available_dirs = set()
        if os.path.isdir(base):
            for d in os.listdir(base):
                if os.path.isdir(os.path.join(base, d)):
                    self.available_dirs.add(d)
        print(f"[Emotion] Base: {base}, available: {sorted(self.available_dirs)}")

    def set_display_callback(self, callback):
        """Update display callback at runtime"""
        self._display_cb = callback

    def analyze_emotion(self, text):
        """Analyze text and return emotion name"""
        if not text:
            return DEFAULT_EMOTION

        text_lower = text.lower()
        best_match = DEFAULT_EMOTION
        best_score = 0

        for emotion, info in EMOTION_MAP.items():
            if info["dir"] not in self.available_dirs:
                continue
            score = 0
            for kw in info["keywords_cn"] + info["keywords_en"]:
                if kw in text_lower:
                    score += len(kw)  # Longer match = higher score
            if score > best_score:
                best_score = score
                best_match = info["dir"]

        return best_match

    def _load_frames(self, emotion_dir):
        """Load expression frames from directory"""
        if emotion_dir in self._frame_cache:
            return self._frame_cache[emotion_dir]

        dir_path = os.path.join(self.expression_base, emotion_dir)
        if not os.path.isdir(dir_path):
            return []

        # Find numbered PNG files
        files = sorted(glob.glob(os.path.join(dir_path, "*.png")))
        if not files:
            return []

        frames = []
        for f in files:
            try:
                img = Image.open(f).convert("RGB")
                # Resize to screen size (320x240)
                if img.size != (320, 240):
                    img = img.resize((320, 240), Image.LANCZOS)
                frames.append(img)
            except Exception as e:
                print(f"[Emotion] Failed to load frame {f}: {e}")

        self._frame_cache[emotion_dir] = frames
        print(f"[Emotion] Loaded {len(frames)} frames for '{emotion_dir}'")
        return frames

    def play_expression(self, emotion_dir, fps=15, loop=True):
        """Play expression animation (non-blocking)"""
        self.stop_expression()

        if emotion_dir not in self.available_dirs:
            emotion_dir = DEFAULT_EMOTION
        if emotion_dir not in self.available_dirs:
            return

        frames = self._load_frames(emotion_dir)
        if not frames:
            return

        self._stop_animation = False
        self._animation_thread = threading.Thread(
            target=self._play_loop, args=(frames, fps, loop), daemon=True
        )
        self._animation_thread.start()

    def _play_loop(self, frames, fps, loop):
        """Animation playback loop"""
        interval = 1.0 / fps
        cb = self._display_cb

        # Single frame: display once and wait until stopped
        if len(frames) == 1:
            if cb:
                try:
                    cb(frames[0])
                except Exception:
                    pass
            while not self._stop_animation:
                time.sleep(0.1)
            return

        while not self._stop_animation:
            for frame in frames:
                if self._stop_animation:
                    break
                if cb:
                    try:
                        cb(frame)
                    except Exception:
                        pass
                time.sleep(interval)
            if not loop:
                break

    def stop_expression(self):
        """Stop current animation"""
        self._stop_animation = True
        if self._animation_thread and self._animation_thread.is_alive():
            self._animation_thread.join(timeout=1)
        self._animation_thread = None

    def play_for_text(self, text, fps=15, loop=True):
        """Analyze text emotion and play corresponding expression"""
        emotion = self.analyze_emotion(text)
        print(f"[Emotion] Text emotion: '{emotion}' for: '{text[:30]}...'")
        self.play_expression(emotion, fps=fps, loop=loop)
        return emotion

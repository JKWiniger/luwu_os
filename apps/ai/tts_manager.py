# -*- coding: utf-8 -*-
"""TTS Manager - Aliyun / Deepgram unified interface"""

import os
import json
import time
import base64
import asyncio
import tempfile
import threading
import re
import struct
from typing import Optional

try:
    import pyaudio
except ImportError:
    pyaudio = None

try:
    import websockets
except ImportError:
    websockets = None

try:
    import websocket
except ImportError:
    websocket = None


# PCM 16-bit gain boost: amplify quiet TTS audio to match system volume
def _amplify_pcm16(data: bytes, gain: float = 2.0) -> bytes:
    """Amplify 16-bit PCM audio data by a gain factor with clipping protection"""
    if gain == 1.0 or not data:
        return data
    # Unpack as signed 16-bit little-endian samples
    n_samples = len(data) // 2
    if n_samples == 0:
        return data
    samples = struct.unpack(f'<{n_samples}h', data[:n_samples * 2])
    # Apply gain with clipping
    amplified = []
    for s in samples:
        v = int(s * gain)
        if v > 32767:
            v = 32767
        elif v < -32768:
            v = -32768
        amplified.append(v)
    return struct.pack(f'<{n_samples}h', *amplified)


class BaseTTS:
    def __init__(self, config):
        self.config = config

    @property
    def supports_session(self):
        """Whether this TTS supports session-based API
        (start_session / send_text / finish_session)"""
        return False

    def speak_sentence(self, text):
        raise NotImplementedError

    def cleanup(self):
        pass


class AliyunTTS(BaseTTS):
    """Aliyun streaming TTS via WebSocket (session-based)

    Usage for a conversation round:
        tts.start_session()      # open WS + configure once
        tts.send_text(sentence1) # append text (can call many times)
        tts.send_text(sentence2)
        tts.finish_session()     # trigger synthesis & wait for playback

    Fallback: speak_sentence() still works (opens+sends+finishes in one call).
    """

    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.voice = config.get("voice", "Cherry")
        self.model = config.get("model", "qwen3-tts-flash-realtime")
        self.base_url = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=" + self.model
        self.sample_rate = 24000
        self.gain = config.get("gain", 2.0)  # PCM volume boost
        self._pyaudio_inst = None
        self._audio_stream = None
        # Session state
        self._ws = None
        self._loop = None
        self._loop_thread = None
        self._session_ready = threading.Event()
        self._session_done = threading.Event()
        self._audio_chunks = 0

    @property
    def supports_session(self):
        return True

    def _init_audio(self):
        if self._pyaudio_inst is None:
            self._pyaudio_inst = pyaudio.PyAudio()
            self._audio_stream = self._pyaudio_inst.open(
                format=pyaudio.paInt16, channels=1,
                rate=self.sample_rate, output=True,
                frames_per_buffer=1024
            )

    # ---- Session-based API (preferred) ----

    def start_session(self):
        """Open WebSocket and configure session (call once per conversation round)"""
        self._session_ready.clear()
        self._session_done.clear()
        self._audio_chunks = 0
        self._init_audio()

        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_session_loop, daemon=True)
        self._loop_thread.start()

        if not self._session_ready.wait(timeout=10):
            print("[AliyunTTS] Session start timeout")
            return False
        print("[AliyunTTS] Session started")
        return True

    def send_text(self, text):
        """Append text to the open session (non-blocking, can call many times)"""
        if not text or not text.strip():
            return
        text = re.sub(r"[\U0001F300-\U0001F9FF]", "", text).strip()
        if not text:
            return
        if not self._ws or not self._loop or self._loop.is_closed():
            print("[AliyunTTS] No active session, falling back to speak_sentence")
            self.speak_sentence(text)
            return
        print(f"[AliyunTTS] Sending text: '{text[:60]}'")
        try:
            fut = asyncio.run_coroutine_threadsafe(
                self._ws.send(json.dumps({
                    "event_id": f"evt_{int(time.time()*1000)}",
                    "type": "input_text_buffer.append",
                    "text": text
                })),
                self._loop
            )
            fut.result(timeout=5)
        except Exception as e:
            print(f"[AliyunTTS] send_text error: {e}")

    def finish_session(self):
        """Send finish signal and wait for all audio playback to complete"""
        if not self._ws or not self._loop or self._loop.is_closed():
            print("[AliyunTTS] No active session to finish")
            return
        try:
            fut = asyncio.run_coroutine_threadsafe(
                self._ws.send(json.dumps({
                    "event_id": f"evt_{int(time.time()*1000)}",
                    "type": "session.finish"
                })),
                self._loop
            )
            fut.result(timeout=5)
        except Exception as e:
            print(f"[AliyunTTS] finish_session send error: {e}")

        # Wait for audio playback to complete
        self._session_done.wait(timeout=60)
        print(f"[AliyunTTS] Session finished, played {self._audio_chunks} audio chunks")
        self._ws = None

    def _run_session_loop(self):
        """Background thread running the asyncio event loop for WebSocket"""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._session_coroutine())
        except Exception as e:
            print(f"[AliyunTTS] Session loop error: {e}")
        finally:
            try:
                self._loop.close()
            except Exception:
                pass

    async def _session_coroutine(self):
        """Main session coroutine: connect, configure, then receive audio"""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            print(f"[AliyunTTS] Connecting to {self.base_url[:60]}...")
            async with websockets.connect(self.base_url, additional_headers=headers) as ws:
                self._ws = ws

                # Configure session
                await ws.send(json.dumps({
                    "event_id": f"evt_{int(time.time()*1000)}",
                    "type": "session.update",
                    "session": {
                        "mode": "server_commit",
                        "voice": self.voice,
                        "language_type": "Auto",
                        "response_format": "pcm",
                        "sample_rate": self.sample_rate
                    }
                }))

                # Wait for session ready
                ready = False
                for _ in range(20):
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
                    if data.get("type") == "session.updated":
                        ready = True
                        print("[AliyunTTS] Session ready")
                        break
                    elif data.get("type") == "session.created":
                        continue
                    elif data.get("type") == "error":
                        print(f"[AliyunTTS] Session error: {data}")
                        return

                if not ready:
                    print("[AliyunTTS] Session not ready")
                    return

                self._session_ready.set()

                # Receive audio until session.finished
                async for message in ws:
                    data = json.loads(message)
                    evt = data.get("type", "")
                    if evt == "response.audio.delta":
                        audio_bytes = base64.b64decode(data.get("delta", ""))
                        if self._audio_stream and audio_bytes:
                            self._audio_stream.write(_amplify_pcm16(audio_bytes, self.gain))
                            self._audio_chunks += 1
                    elif evt == "session.finished":
                        break
                    elif evt == "response.done":
                        continue  # More audio may follow in server_commit
                    elif evt == "error":
                        print(f"[AliyunTTS] Stream error: {data}")
                        break

                print(f"[AliyunTTS] Played {self._audio_chunks} audio chunks")
        except Exception as e:
            print(f"[AliyunTTS] WebSocket error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._ws = None
            self._session_done.set()

    # ---- Legacy single-sentence API (fallback / Deepgram compat) ----

    def speak_sentence(self, text):
        """Speak a single sentence (opens a session, sends, finishes)"""
        if not text or not text.strip():
            return
        text = re.sub(r"[\U0001F300-\U0001F9FF]", "", text).strip()
        if not text:
            return
        print(f"[AliyunTTS] speak_sentence: '{text[:50]}...'")
        if self.start_session():
            self.send_text(text)
            self.finish_session()

    def cleanup(self):
        # Close active session
        if self._ws and self._loop and not self._loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop).result(timeout=3)
            except Exception:
                pass
        # Release audio resources
        try:
            if self._audio_stream:
                self._audio_stream.stop_stream()
                self._audio_stream.close()
        except Exception:
            pass
        try:
            if self._pyaudio_inst:
                self._pyaudio_inst.terminate()
        except Exception:
            pass
        self._audio_stream = None
        self._pyaudio_inst = None
        self._ws = None


class DeepgramTTS(BaseTTS):
    """Deepgram WebSocket streaming Text-to-Speech

    Official docs: https://developers.deepgram.com/docs/tts-websocket-streaming

    WebSocket endpoint: wss://api.deepgram.com/v1/speak
    Uses JSON events for control and binary frames for audio.

    Query parameters:
      - model: aura-2-thalia-en / aura-2-luna-en / aura-2-stella-en etc.
      - encoding: linear16
      - sample_rate: 48000 / 24000 / 16000 etc.

    Event flows:
      1. Connect with Token header
      2. Client → Server: {"type": "Speak", "text": "..."}
      3. Server → Client: binary audio frames
      4. Client → Server: {"type": "Flush"}  (signal end of text)
      5. Client → Server: {"type": "Close"}  (close connection)

    Supports session-based API: start_session / send_text / finish_session
    """

    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "aura-2-thalia-en")
        self.sample_rate = config.get("sample_rate", 48000)
        self.gain = config.get("gain", 2.0)
        self._pyaudio_inst = None
        self._audio_stream = None
        # Session state
        self._ws = None
        self._ws_thread = None
        self._session_ready = threading.Event()
        self._session_done = threading.Event()
        self._flushed = threading.Event()  # Set when server confirms all audio sent
        self._audio_chunks = 0
        self._error = None
        self.ws_url = f"wss://api.deepgram.com/v1/speak?model={self.model}&encoding=linear16&sample_rate={self.sample_rate}"

    @property
    def supports_session(self):
        return True

    def _init_audio(self):
        if self._pyaudio_inst is None:
            self._pyaudio_inst = pyaudio.PyAudio()
            self._audio_stream = self._pyaudio_inst.open(
                format=pyaudio.paInt16, channels=1,
                rate=self.sample_rate, output=True,
                frames_per_buffer=1024
            )

    # ---- Session-based API ----

    def start_session(self):
        """Open WebSocket connection to Deepgram (call once per conversation round)"""
        self._session_ready.clear()
        self._session_done.clear()
        self._flushed.clear()
        self._audio_chunks = 0
        self._error = None
        self._init_audio()

        result = {"connected": False, "ready": True}  # Deepgram is ready instantly after connect

        def on_open(ws):
            result["connected"] = True
            self._session_ready.set()  # Unblock start_session wait
            print("[DeepgramTTS] WebSocket connected")

        def on_message(ws, message):
            # Deepgram sends binary for audio, JSON for events
            if isinstance(message, bytes):
                if self._audio_stream:
                    self._audio_stream.write(_amplify_pcm16(message, self.gain))
                    self._audio_chunks += 1
                return

            try:
                data = json.loads(message)
                msg_type = data.get("type", "")
                if msg_type == "Flushed":
                    print(f"[DeepgramTTS] Flushed (all audio sent)")
                    self._flushed.set()
                elif msg_type == "Error":
                    err_msg = data.get("message", "Unknown error")
                    print(f"[DeepgramTTS] Server error: {err_msg}")
                    self._error = err_msg
                    self._flushed.set()
                    self._session_done.set()
                elif msg_type == "Close":
                    self._session_done.set()
            except Exception as e:
                print(f"[DeepgramTTS] Message parse error: {e}")

        def on_error(ws, error):
            print(f"[DeepgramTTS] WebSocket error: {error}")
            self._error = str(error)
            self._session_done.set()

        def on_close(ws, code, msg):
            if code and code != 1000:
                print(f"[DeepgramTTS] WebSocket closed: code={code}, msg='{msg}'")
            self._session_done.set()

        self._ws = websocket.WebSocketApp(
            self.ws_url,
            header=[f"Authorization: Token {self.api_key}"],
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        self._ws_thread = threading.Thread(target=self._ws.run_forever, daemon=True)
        self._ws_thread.start()

        # Wait for connection (up to 15s for high-latency networks)
        if not self._session_ready.wait(timeout=15):
            print("[DeepgramTTS] Connection timeout (>15s)")
            return False

        if self._error:
            print(f"[DeepgramTTS] Connection error: {self._error}")
            return False

        print("[DeepgramTTS] Session started")
        return True

    def send_text(self, text):
        """Send text to synthesize (non-blocking)"""
        if not text or not text.strip():
            return
        text = re.sub(r"[\U0001F300-\U0001F9FF]", "", text).strip()
        if not text:
            return
        if not self._ws:
            print("[DeepgramTTS] No active session")
            return
        print(f"[DeepgramTTS] Sending: '{text[:60]}'")
        try:
            self._ws.send(json.dumps({"type": "Speak", "text": text}))
        except Exception as e:
            print(f"[DeepgramTTS] send_text error: {e}")
            self._error = str(e)

    def finish_session(self):
        """Send Flush and wait for Flushed confirmation, then Close.

        Deepgram event flow:
          Client → {"type": "Flush"}
          Server → [remaining binary audio frames]
          Server → {"type": "Flushed"}   ← all audio has been sent
          Client → {"type": "Close"}
        """
        if not self._ws:
            print("[DeepgramTTS] No active session to finish")
            return

        try:
            self._ws.send(json.dumps({"type": "Flush"}))
            print("[DeepgramTTS] Flush sent, waiting for Flushed...")
        except Exception as e:
            print(f"[DeepgramTTS] Flush error: {e}")

        # Wait for "Flushed" event = server confirms all audio has been sent
        if not self._flushed.wait(timeout=30):
            print("[DeepgramTTS] Warning: Flushed event not received (timeout)")

        # Send Close to properly end the connection
        try:
            self._ws.send(json.dumps({"type": "Close"}))
        except Exception:
            pass

        # Wait for PyAudio hardware buffer to drain (~600ms covers ALSA + speaker)
        if self._audio_chunks > 0:
            time.sleep(0.6)

        print(f"[DeepgramTTS] Session finished, played {self._audio_chunks} chunks")
        self._ws = None

    # ---- Legacy single-sentence API ----

    def speak_sentence(self, text):
        """Speak a single sentence (opens session, sends, finishes)"""
        if not text or not text.strip():
            return
        text = re.sub(r"[\U0001F300-\U0001F9FF]", "", text).strip()
        if not text:
            return
        print(f"[DeepgramTTS] speak_sentence: '{text[:50]}...'")
        if self.start_session():
            self.send_text(text)
            self.finish_session()

    def cleanup(self):
        # Close active session
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        # Release audio resources
        try:
            if self._audio_stream:
                self._audio_stream.stop_stream()
                self._audio_stream.close()
        except Exception:
            pass
        try:
            if self._pyaudio_inst:
                self._pyaudio_inst.terminate()
        except Exception:
            pass
        self._audio_stream = None
        self._pyaudio_inst = None
        self._ws = None


def create_tts(config):
    """Create TTS instance based on config"""
    provider = config.get("provider", "aliyun")
    if provider == "deepgram":
        return DeepgramTTS(config.get("deepgram", {}))
    else:
        return AliyunTTS(config.get("aliyun", {}))

# -*- coding: utf-8 -*-
"""Function Call tools - wraps robot_tools for robot control + VLM photo"""

import os
import sys
import time
import base64
import json
from typing import Dict, List

# Import robot_tools from local copy (avoid mixing venvs)
_voice_chat_tools = None
_tool_executor = None

def _init_tools():
    global _voice_chat_tools, _tool_executor
    if _voice_chat_tools is not None:
        return
    try:
        from robot_tools import (
            get_tool_definitions,
            VoiceChatToolExecutor,
            is_hardware_available,
            get_model_type,
        )
        _voice_chat_tools = {
            "get_tool_definitions": get_tool_definitions,
            "VoiceChatToolExecutor": VoiceChatToolExecutor,
            "is_hardware_available": is_hardware_available,
            "get_model_type": get_model_type,
        }
        print(f"[Tools] robot_tools loaded, model={get_model_type()}, hw={is_hardware_available()}")
    except Exception as e:
        print(f"[Tools] Failed to import robot_tools: {e}")
        _voice_chat_tools = {}


# Additional VLM photo tool (uses LLM's VLM capability instead of separate VLM)
VLM_PHOTO_TOOL = {
    "type": "function",
    "function": {
        "name": "take_photo_and_understand",
        "description": "Take a photo with the robot camera and use AI vision to understand what's in the image. Use this when user asks to look at something, take a photo, or identify objects.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "What to ask about the photo, e.g. 'What do you see?' or 'Describe this scene'"
                }
            },
            "required": ["prompt"]
        }
    }
}


class ToolManager:
    """Manages Function Call tools for LLM"""

    def __init__(self, llm_api_key=""):
        _init_tools()
        self.llm_api_key = llm_api_key
        self._executor = None
        self._photo_callback = None  # callback for VLM photo: (prompt) -> str

        if _voice_chat_tools and "VoiceChatToolExecutor" in _voice_chat_tools:
            try:
                self._executor = _voice_chat_tools["VoiceChatToolExecutor"](llm_api_key)
                print("[Tools] VoiceChatToolExecutor initialized")
            except Exception as e:
                print(f"[Tools] VoiceChatToolExecutor init error: {e}")

    def set_photo_callback(self, callback):
        """Set VLM photo callback: callback(prompt) -> description_str"""
        self._photo_callback = callback

    def get_tool_definitions(self) -> List[Dict]:
        """Get all tool definitions for LLM"""
        tools = []
        if _voice_chat_tools and "get_tool_definitions" in _voice_chat_tools:
            try:
                tools = list(_voice_chat_tools["get_tool_definitions"]())
            except Exception as e:
                print(f"[Tools] get_tool_definitions error: {e}")

        # Add VLM photo tool (uses LLM's own VLM, replaces xgo_photo_understand)
        # Filter out robot_tools' xgo_photo_understand to avoid hardcoded Aliyun VLM
        tools = [t for t in tools if t.get("function", {}).get("name") != "xgo_photo_understand"]
        tools.append(VLM_PHOTO_TOOL)
        return tools

    def execute(self, tool_name: str, arguments: Dict) -> str:
        """Execute a tool by name"""
        # Handle VLM photo separately
        if tool_name == "take_photo_and_understand":
            return self._execute_photo(arguments)

        # Delegate to robot_tools executor
        if self._executor:
            try:
                return self._executor.execute(tool_name, arguments)
            except Exception as e:
                return f"Tool error: {e}"

        return f"Tool '{tool_name}' not available (hardware not initialized)"

    def _execute_photo(self, arguments: Dict) -> str:
        """Take photo and understand using VLM callback"""
        prompt = arguments.get("prompt", "What do you see?")

        if self._photo_callback:
            try:
                return self._photo_callback(prompt)
            except Exception as e:
                return f"Photo error: {e}"

        # Fallback: try to capture and return base64
        try:
            return self._capture_and_describe_fallback(prompt)
        except Exception as e:
            return f"Photo capture failed: {e}"

    def _capture_and_describe_fallback(self, prompt: str) -> str:
        """Fallback photo capture using picamera2 directly"""
        try:
            import cv2
            from picamera2 import Picamera2

            photo_path = "/tmp/ai_chat_photo.jpg"
            picam2 = Picamera2()
            picam2.configure(picam2.create_preview_configuration(
                main={"format": "RGB888", "size": (640, 480)}
            ))
            picam2.start()
            time.sleep(0.5)
            image = picam2.capture_array()  # RGB888 format
            cv2.imwrite(photo_path, cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
            picam2.stop()

            with open(photo_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")

            return f"__VLM_PHOTO__|{prompt}|{img_b64}"
        except Exception as e:
            return f"Camera not available: {e}"

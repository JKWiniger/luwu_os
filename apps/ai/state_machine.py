# -*- coding: utf-8 -*-
"""State Machine for AI Chat"""

from enum import Enum
import threading


class State(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class StateMachine:
    """Simple state machine with callbacks"""

    def __init__(self):
        self.state = State.IDLE
        self._callbacks = []
        self._lock = threading.Lock()

    def on_state_changed(self, callback):
        """Register callback: callback(old_state, new_state)"""
        self._callbacks.append(callback)

    def set_state(self, new_state):
        with self._lock:
            if self.state == new_state:
                return
            old = self.state
            self.state = new_state
            print(f"[State] {old.value} -> {new_state.value}")
            for cb in self._callbacks:
                try:
                    cb(old, new_state)
                except Exception as e:
                    print(f"[State] Callback error: {e}")

    def is_idle(self):
        return self.state == State.IDLE

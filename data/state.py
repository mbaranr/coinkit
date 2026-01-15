import json
import os
from threading import Lock

STATE_FILE = "state.json"
_LOCK = Lock()


def _load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def _save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def init_db():
    if not os.path.exists(STATE_FILE):
        _save_state({})


def get_last_value(key):
    with _LOCK:
        state = _load_state()
        value = state.get(key)
        return float(value) if value is not None else None


def save_value(key, value):
    with _LOCK:
        state = _load_state()
        state[key] = float(value)
        _save_state(state)
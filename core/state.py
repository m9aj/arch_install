# core/state.py
# State is stored in state.json in the logs directory.
# Tracks completed, skipped, and failed steps to ensure idempotency.

import json
import os
import tempfile

from core.config import LOGS_DIR

STATE_FILE = os.path.join(LOGS_DIR, "state.json")


def _load():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    # Atomic write via temporary file in the same directory to avoid half-written state on crash
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(STATE_FILE), prefix="state_", suffix=".tmp")
    try:
        with open(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, STATE_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def is_done(name):
    """Return True if step is done or skipped, preventing it from running again."""
    status = _load().get(name)
    return status in ["done", "skipped"]


def mark_done(name):
    state = _load()
    state[name] = "done"
    _save(state)


def mark_skipped(name):
    """Explicitly mark a step as skipped (e.g., if disabled in YAML)."""
    state = _load()
    state[name] = "skipped"
    _save(state)


def mark_failed(name):
    """Mark a step as failed (optional, can help in debugging state.json)."""
    state = _load()
    state[name] = "failed"
    _save(state)


def reset(name):
    """Clear a single step so it reruns on next execution."""
    state = _load()
    state.pop(name, None)
    _save(state)


def reset_all():
    """Wipe all state — forces a full rerun."""
    _save({})

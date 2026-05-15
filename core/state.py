# core/state.py
# State is stored in state.json in the project root (alongside the installer).
# Since the project lives on the Personal drive, this file persists across
# reinstalls and is readable in ~/Arch/arch_install_py_cl/ after installation.

import os
import json

from core.helper_core import LOGS_DIR

STATE_FILE = os.path.join(LOGS_DIR, "state.json")


def _load():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE) as f:
        return json.load(f)


def _save(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


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

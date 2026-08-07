# core/helper_gnome.py

import os
from core.shell import run

def _is_gnome(config):
    return config.get("arch", {}).get("de") == "gnome"

def normalize_desktop_name(name):
    name = str(name)
    return name if name.endswith(".desktop") else f"{name}.desktop"

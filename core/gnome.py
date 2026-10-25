# core/helper_gnome.py

import os
from core.shell import run

def get_des(config):
    de = config.get("arch", {}).get("de", [])
    if isinstance(de, str):
        return [d.strip() for d in de.split(",") if d.strip()]
    if isinstance(de, list):
        return [str(d).strip() for item in de for d in str(item).split(",") if str(d).strip()]
    return []

def _is_gnome(config):
    return "gnome" in get_des(config)

def _is_hyprland(config):
    return "hyprland" in get_des(config)

def _is_kde(config):
    return "kde" in get_des(config)

def normalize_desktop_name(name):
    name = str(name)
    return name if name.endswith(".desktop") else f"{name}.desktop"

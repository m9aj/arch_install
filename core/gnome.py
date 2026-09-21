# core/helper_gnome.py

import os
from core.shell import run

def _is_gnome(config):
    de = config.get("arch", {}).get("de", [])
    if isinstance(de, str):
        return de == "gnome"
    if isinstance(de, list):
        return "gnome" in de
    return False

def _is_hyprland(config):
    de = config.get("arch", {}).get("de", [])
    if isinstance(de, str):
        return de == "hyprland"
    if isinstance(de, list):
        return "hyprland" in de
    return False

def _is_kde(config):
    de = config.get("arch", {}).get("de", [])
    if isinstance(de, str):
        return de == "kde"
    if isinstance(de, list):
        return "kde" in de
    return False

def normalize_desktop_name(name):
    name = str(name)
    return name if name.endswith(".desktop") else f"{name}.desktop"

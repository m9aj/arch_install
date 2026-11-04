# postreboot/status_cli.py
# Displays the current execution status of arch_install steps and features.
# Usage: ./arch-install status

import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.config import detect_profile, load_yaml, merge_dicts, LOGS_DIR
import yaml

USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ

PHASE1_STEPS = [
    ("disk", "Partition & format / subvolume handling"),
    ("mount", "Mount subvolume tree & EFI"),
    ("pacstrap", "Install base & core system packages"),
    ("fstab", "Generate fstab & custom mounts"),
    ("config", "Locale, timezone, hostname, users, network"),
    ("tweaks", "makepkg flags, pacman color, sysctl, journald"),
    ("packages", "Install post-base packages"),
    ("services", "Enable core systemd services"),
    ("bootloader", "Install bootloader & UKI initramfs"),
]

PHASE2_STEPS = [
    ("user_dirs", "User directories & XDG bindings"),
    ("dotfiles", "Chezmoi dotfiles deployment"),
    ("bluetooth", "Bluetooth state restoration"),
    ("network_hosts", "Static network host entries"),
    ("aur_helper", "Build & install AUR helper (paru/yay)"),
    ("features", "Run enabled system features"),
    ("aur_packages", "Install machine AUR packages"),
    ("themes", "Cursor & wallpaper themes"),
    ("citrix", "Citrix Workspace configuration"),
    ("gnome_setup", "GNOME desktop & dconf configuration"),
    ("hyprland_setup", "Hyprland / Impasto desktop setup"),
]


def _c(text, color_code):
    return f"\033[{color_code}m{text}\033[0m" if USE_COLOR else text


def _format_status(status):
    if status == "done":
        return _c("[DONE]   ", "1;32")
    elif status == "skipped":
        return _c("[SKIPPED]", "1;33")
    elif status == "failed":
        return _c("[FAILED] ", "1;31")
    else:
        return _c("[PENDING]", "2")


def _load_state():
    state_file = os.path.join(LOGS_DIR, "state.yaml")
    if not os.path.exists(state_file):
        return {}
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def show_status():
    profile = detect_profile()
    state = _load_state()

    print(_c("\n========================================================", "1;34"))
    profile_str = f" (Profile: {_c(profile, '1;32')})" if profile else " (No profile marker detected)"
    print(_c(f" ARCH INSTALL EXECUTION STATUS{profile_str}", "1;36"))
    print(_c("========================================================\n", "1;34"))

    # Phase 1
    print(_c("--- Phase 1: Pre-Reboot Steps ---", "1;33"))
    for step_id, desc in PHASE1_STEPS:
        entry = state.get(step_id, {})
        status = entry.get("status") if isinstance(entry, dict) else (entry if isinstance(entry, str) else None)
        ts = f" ({entry.get('timestamp')})" if isinstance(entry, dict) and entry.get("timestamp") else ""
        print(f"  {_format_status(status)}  {_c(step_id, '1'):16s}  {desc}{ts}")

    # Phase 2
    print(_c("\n--- Phase 2: Post-Reboot Steps ---", "1;33"))
    for step_id, desc in PHASE2_STEPS:
        entry = state.get(step_id, {})
        status = entry.get("status") if isinstance(entry, dict) else (entry if isinstance(entry, str) else None)
        ts = f" ({entry.get('timestamp')})" if isinstance(entry, dict) and entry.get("timestamp") else ""
        print(f"  {_format_status(status)}  {_c(step_id, '1'):16s}  {desc}{ts}")

    # Features
    print(_c("\n--- System Features ---", "1;33"))
    base_cfg = load_yaml("profiles/base.yaml") or {}
    if profile:
        try:
            prof_data = load_yaml(f"profiles/{profile}.yaml") or {}
            base_cfg = merge_dicts(base_cfg, prof_data)
        except Exception:
            pass

    features_cfg = base_cfg.get("features", {})
    feat_files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "features", "*.py")))

    for path in feat_files:
        fname = os.path.basename(path)[:-3]
        if fname == "__init__":
            continue

        cfg_entry = features_cfg.get(fname, {})
        is_cfg_enabled = False
        if isinstance(cfg_entry, bool):
            is_cfg_enabled = cfg_entry
        elif isinstance(cfg_entry, dict):
            server_block = cfg_entry.get("server")
            is_cfg_enabled = server_block.get("enabled", False) if isinstance(server_block, dict) else cfg_entry.get("enabled", False)

        cfg_badge = _c("[configured: on ]", "32") if is_cfg_enabled else _c("[configured: off]", "2")

        entry = state.get(f"feature.{fname}", {})
        status = entry.get("status") if isinstance(entry, dict) else (entry if isinstance(entry, str) else None)
        print(f"  {_format_status(status)}  {cfg_badge}  {_c(fname, '1')}")

    print()


def main():
    show_status()


if __name__ == "__main__":
    main()

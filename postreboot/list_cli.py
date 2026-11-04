# postreboot/list_cli.py
# Lists available features and package groups in arch_install.
# Usage:
#   ./arch-install list                  List all features and package groups
#   ./arch-install list features         List only system features
#   ./arch-install list packages         List only package groups

import glob
import importlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.config import detect_profile, load_yaml, merge_dicts

USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _c(text, color_code):
    return f"\033[{color_code}m{text}\033[0m" if USE_COLOR else text


def _load_effective_features():
    """Load effective feature states from base.yaml + active profile without prompting for secrets."""
    base = load_yaml("profiles/base.yaml") or {}
    prof = detect_profile()
    if prof:
        try:
            prof_data = load_yaml(f"profiles/{prof}.yaml") or {}
            base = merge_dicts(base, prof_data)
        except Exception:
            pass
    return base.get("features", {}), prof


def list_features():
    features_cfg, active_profile = _load_effective_features()
    profile_info = f" (profile: {active_profile})" if active_profile else ""

    print(_c("\n========================================================", "1;34"))
    print(_c(f" SYSTEM FEATURES (features/*.py){profile_info}", "1;36"))
    print(_c("========================================================\n", "1;34"))

    feat_files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "features", "*.py")))

    for path in feat_files:
        name = os.path.basename(path)[:-3]
        if name == "__init__":
            continue

        desc = ""
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s.startswith("#") and not s.startswith("# features/"):
                    desc = s.lstrip("#").strip()
                    break

        pkgs = []
        try:
            mod = importlib.import_module(f"features.{name}")
            pacman = getattr(mod, "PACMAN_PACKAGES", [])
            aur = getattr(mod, "AUR_PACKAGES", [])
            pkgs = list(pacman) + [f"{p} (AUR)" for p in aur]
        except Exception:
            pass

        cfg_entry = features_cfg.get(name, {})
        is_enabled = None
        if isinstance(cfg_entry, dict):
            server_block = cfg_entry.get("server")
            if server_block is not None:
                is_enabled = server_block.get("enabled", False)
            else:
                is_enabled = cfg_entry.get("enabled")

        status_str = ""
        if is_enabled is True:
            status_str = _c("[enabled]", "32")
        elif is_enabled is False:
            status_str = _c("[disabled]", "2")

        header = f"  {_c(name, '1')} {status_str}"
        print(header)
        if desc:
            print(f"    {desc}")
        if pkgs:
            print(f"    {_c('Packages:', '2')} {', '.join(pkgs)}")
        print()

    print(_c("Run a single feature:", "1"))
    print(f"  ./arch-install feature <name> [profile]\n")


def list_packages():
    data = load_yaml("package_profiles.yaml") or {}
    post_profiles = data.get("post_profiles", {})
    core_profiles = data.get("core_profiles", {})

    print(_c("\n========================================================", "1;34"))
    print(_c(" PACKAGE GROUPS (config/package_profiles.yaml)", "1;36"))
    print(_c("========================================================\n", "1;34"))

    print(_c("--- Post-Installation Groups ---", "1;33"))
    for name, item in post_profiles.items():
        if isinstance(item, dict):
            pkgs = item.get("packages", [])
            svcs = item.get("services", [])
        else:
            pkgs = item or []
            svcs = []

        svc_str = f" {_c('[services: ' + ', '.join(svcs) + ']', '35')}" if svcs else ""
        print(f"  {_c(name, '1'):20s} -> {', '.join(pkgs)}{svc_str}")

    print(_c("\n--- Core System Groups ---", "1;33"))
    for name, item in core_profiles.items():
        pkgs = item if isinstance(item, list) else (item.get("packages", []) if isinstance(item, dict) else [])
        print(f"  {_c(name, '1'):20s} -> {', '.join(pkgs or [])}")

    hw_profiles = data.get("hardware_packages", {})
    if hw_profiles:
        print(_c("\n--- Hardware Drivers & Microcode ---", "1;33"))
        for hw_type, mapping in hw_profiles.items():
            for hw_name, pkgs in mapping.items():
                label = f"{hw_type}:{hw_name}"
                print(f"  {_c(label, '1'):20s} -> {', '.join(pkgs or [])}")

    print(_c("\nInstall package group(s):", "1"))
    print(f"  ./arch-install pkg <group> [group2 ...]\n")


def main():
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    if target in ("features", "feature", "feat", "-f"):
        list_features()
    elif target in ("packages", "package", "pkg", "pkgs", "groups", "-p"):
        list_packages()
    elif target in ("all", "list", "-a"):
        list_features()
        list_packages()
    elif target in ("help", "--help", "-h"):
        print("Usage:")
        print("  ./arch-install list                  List all features and package groups")
        print("  ./arch-install list features         List only system features")
        print("  ./arch-install list packages         List only package groups")
    else:
        print(f"[ERROR] Unknown target: {target}")
        print("Valid options: features, packages, all")
        sys.exit(1)


if __name__ == "__main__":
    main()

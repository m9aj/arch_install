# postreboot/pkg_cli.py
# Standalone package profile runner — installs packages (and enables services)
# for one or more named groups from config/package_profiles.yaml.
# Usage:
#   ./arch-install pkg                 List available package groups
#   ./arch-install pkg <group> [...]   Install package group(s)

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.config import load_yaml, detect_profile, load_profile_config, LOGS_DIR
from core.logger import logger, setup as setup_logger, set_stderr_log
from core.installer import install_packages
from core.shell import run


def _list_groups(post_profiles, core_profiles):
    print("Available package groups (from config/package_profiles.yaml):\n")
    print("  Post-install groups:")
    for name, info in post_profiles.items():
        pkgs = info.get("packages", []) if isinstance(info, dict) else (info or [])
        svcs = info.get("services", []) if isinstance(info, dict) else []
        svc_suffix = f"  [services: {', '.join(svcs)}]" if svcs else ""
        print(f"    {name:18s} -> {', '.join(pkgs)}{svc_suffix}")
    print("\n  Core groups:")
    for name, pkgs in core_profiles.items():
        print(f"    {name:18s} -> {', '.join(pkgs or [])}")
    print("\nUsage: arch-install pkg <group> [group2 ...]")


def main():
    if os.getuid() == 0:
        print("[ERROR] 'arch-install pkg' must NOT be run as root. Run as your regular user.")
        sys.exit(1)

    profiles_data = load_yaml("package_profiles.yaml") or {}
    post_profiles = profiles_data.get("post_profiles", {})
    core_profiles = profiles_data.get("core_profiles", {})

    args = sys.argv[1:]
    if not args or args[0] in ("list", "-l", "--list", "help", "-h", "--help"):
        _list_groups(post_profiles, core_profiles)
        sys.exit(0)

    unknown = [g for g in args if g not in post_profiles and g not in core_profiles]
    if unknown:
        print(f"[ERROR] Unknown package group(s): {', '.join(unknown)}\n")
        _list_groups(post_profiles, core_profiles)
        sys.exit(1)

    setup_logger(os.path.join(LOGS_DIR, "features.log"))
    set_stderr_log(os.path.join(LOGS_DIR, "features_err.log"))

    profile = detect_profile()
    config = load_profile_config(profile) if profile else {}

    for group in args:
        logger.info(f"[pkg:{group}] Installing package group '{group}'")
        if group in post_profiles:
            entry = post_profiles[group] or {}
            pacman_pkgs = entry.get("packages", []) if isinstance(entry, dict) else list(entry)
            aur_pkgs = entry.get("aur", []) if isinstance(entry, dict) else []
            services = entry.get("services", []) if isinstance(entry, dict) else []
        else:
            pacman_pkgs = list(core_profiles[group] or [])
            aur_pkgs = []
            services = []

        if pacman_pkgs or aur_pkgs:
            install_packages(config, pacman_pkgs=pacman_pkgs, aur_pkgs=aur_pkgs)

        for svc in services:
            logger.info(f"[pkg:{group}] Enabling service: {svc}")
            run(f"sudo systemctl enable --now {svc}")

        logger.info(f"[pkg:{group}] Done.")


if __name__ == "__main__":
    main()

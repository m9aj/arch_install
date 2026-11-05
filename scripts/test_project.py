#!/usr/bin/env python3
# scripts/test_project.py
# Automated test runner and dry-run config validator for arch_install.
# Usage:
#   ./arch-install test              Run all project health and sanity tests
#   ./arch-install check [profile]   Dry-run validate configuration for a profile

import compileall
import contextlib
import importlib
import logging
import os
import pwd
import subprocess
import sys
import traceback
from unittest.mock import MagicMock, patch, mock_open

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from core.config import _discover_profiles, load_profile_config, load_yaml, detect_profile
from core.validator import validate

USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _c(text, color_code):
    return f"\033[{color_code}m{text}\033[0m" if USE_COLOR else text


def test_compile():
    print(_c("1. Testing syntax & compilation...", "1;33"))
    subdirs = ["core", "prereboot", "postreboot", "features"]
    all_ok = True
    for sd in subdirs:
        path = os.path.join(PROJECT_ROOT, sd)
        success = compileall.compile_dir(path, quiet=1)
        if success:
            print(f"   {_c('✓', '32')} {sd}/ compiled successfully")
        else:
            print(f"   {_c('✗', '31')} {sd}/ compilation failed")
            all_ok = False

    res = subprocess.run(["bash", "-n", os.path.join(PROJECT_ROOT, "arch-install")], capture_output=True, text=True)
    if res.returncode == 0:
        print(f"   {_c('✓', '32')} arch-install (shell wrapper) syntax valid")
    else:
        print(f"   {_c('✗', '31')} arch-install shell script syntax error: {res.stderr}")
        all_ok = False

    return all_ok


def test_features():
    print(_c("\n2. Testing feature modules...", "1;33"))
    features_dir = os.path.join(PROJECT_ROOT, "features")
    all_ok = True
    for f in sorted(os.listdir(features_dir)):
        if f.endswith(".py") and not f.startswith("__"):
            name = f[:-3]
            try:
                mod = importlib.import_module(f"features.{name}")
                has_conf = hasattr(mod, "configure")
                pacman = getattr(mod, "PACMAN_PACKAGES", [])
                conf_str = "has configure()" if has_conf else "no configure()"
                print(f"   {_c('✓', '32')} features/{name}.py ({conf_str}, pkgs: {len(pacman)})")
            except Exception as e:
                print(f"   {_c('✗', '31')} features/{name}.py failed to import: {e}")
                all_ok = False
    return all_ok


def test_package_profiles():
    print(_c("\n3. Testing package profiles config...", "1;33"))
    data = load_yaml("package_profiles.yaml")
    if not data:
        print(f"   {_c('✗', '31')} package_profiles.yaml is empty or missing")
        return False

    keys = ["core_profiles", "post_profiles", "hardware_packages"]
    for k in keys:
        if k in data:
            count = len(data[k])
            print(f"   {_c('✓', '32')} {k} verified ({count} groups)")
        else:
            print(f"   {_c('✗', '31')} Missing {k} in package_profiles.yaml")
            return False
    return True


def test_profiles(target_profile=None):
    title = f"Dry-run validating profile '{target_profile}'..." if target_profile else "Testing all profile configurations..."
    print(_c(f"\n4. {title}", "1;33"))

    profiles = [target_profile] if target_profile else _discover_profiles()
    all_ok = True

    for p in profiles:
        try:
            cfg = load_profile_config(p, load_secrets=False)
            if "system" not in cfg:
                cfg["system"] = {}
            if not cfg["system"].get("root_password"):
                cfg["system"]["root_password"] = "mock_root_pw"
            if not cfg["system"].get("user_password"):
                cfg["system"]["user_password"] = "mock_user_pw"

            validate(cfg)
            hostname = cfg.get("system", {}).get("hostname", "unknown")
            kernel = cfg.get("boot", {}).get("kernel", "unknown")
            bootloader = cfg.get("boot", {}).get("bootloader", "unknown")
            print(f"   {_c('✓', '32')} profile '{p}' valid (host: {hostname}, kernel: {kernel}, boot: {bootloader})")
        except Exception as e:
            print(f"   {_c('✗', '31')} profile '{p}' failed validation: {e}")
            all_ok = False

    return all_ok


def test_dry_run(target_profile=None):
    title = f"Simulating dry-run execution for '{target_profile}'..." if target_profile else "Testing simulated dry-run execution (all stages & profiles)..."
    print(_c(f"\n5. {title}", "1;33"))

    profiles = [target_profile] if target_profile else _discover_profiles()
    all_ok = True

    from core.shell import set_mock_runner
    prev_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)

    def mock_run(cmd, *args, **kwargs):
        if "which" in cmd:
            return MagicMock(returncode=0, stdout="/usr/bin/yay", stderr="")
        if "gnome-shell --version" in cmd:
            return MagicMock(returncode=0, stdout="GNOME Shell 47.0", stderr="")
        if "grep" in cmd or "blkid" in cmd:
            return MagicMock(returncode=0, stdout="dummy", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    set_mock_runner(mock_run)

    try:
        for p in profiles:
            cfg = load_profile_config(p, load_secrets=False)
            if "system" not in cfg:
                cfg["system"] = {}
            if not cfg["system"].get("root_password"):
                cfg["system"]["root_password"] = "mock_root_pw"
            if not cfg["system"].get("user_password"):
                cfg["system"]["user_password"] = "mock_user_pw"

            mock_pw = MagicMock(pw_uid=1000, pw_gid=1000)

            orig_open = open
            def safe_open(file, *args, **kwargs):
                sfile = str(file)
                if os.path.isabs(sfile) and sfile.startswith(PROJECT_ROOT):
                    return orig_open(file, *args, **kwargs)
                return mock_open(read_data="127.0.0.1 localhost\nHOOKS=(base udev autodetect block filesystems)\n")(*args, **kwargs)

            mock_part = lambda b, s: f"/dev/disk/by-id/mock-disk{s}"
            mock_root = lambda c: "/dev/disk/by-id/mock-disk-part3"

            patches = [
                patch("core.shell.run", side_effect=mock_run),
                patch("core.disk.get_base_disk", return_value="/dev/disk/by-id/mock-disk"),
                patch("core.disk.get_partition", side_effect=mock_part),
                patch("core.disk.get_root_partition", side_effect=mock_root),
                patch("prereboot.disk.get_partition", side_effect=mock_part),
                patch("prereboot.disk.get_root_partition", side_effect=mock_root),
                patch("prereboot.bootloader.get_partition", side_effect=mock_part),
                patch("prereboot.archinstall.get_partition", side_effect=mock_part),
                patch("core.config._decrypt_age_yaml", return_value={"server": {}, "client": {}}),
                patch("core.state.is_done", return_value=False),
                patch("core.state.mark_done", return_value=None),
                patch("pwd.getpwnam", return_value=mock_pw),
                patch("os.unlink", return_value=None),
                patch("os.symlink", return_value=None),
                patch("os.makedirs", return_value=None),
                patch("shutil.copy", return_value=None),
                patch("shutil.copytree", return_value=None),
                patch("shutil.rmtree", return_value=None),
                patch("shutil.chown", return_value=None),
                patch("os.chown", return_value=None),
                patch("os.chmod", return_value=None),
                patch("os.path.exists", return_value=True),
                patch("os.path.ismount", return_value=True),
                patch("builtins.open", side_effect=safe_open),
                patch("postreboot.gnome._install_extension", return_value="dummy-uuid"),
            ]

            try:
                with contextlib.ExitStack() as stack:
                    for patch_obj in patches:
                        stack.enter_context(patch_obj)

                    from prereboot import disk, archinstall, system, bootloader
                    disk.clean_root(cfg)
                    disk.mount_tree(cfg)
                    archinstall.install_core(cfg)
                    archinstall.generate_fstab(cfg)
                    archinstall.initial_config(cfg)
                    archinstall.initial_tweaks(cfg)
                    system.install_post(cfg)
                    system.enable_services(cfg)
                    bootloader.install_bootloader(cfg)

                    from postreboot import (
                        user_dirs, dotfiles, system_config, aur,
                        themes, gnome, hyprland, features
                    )
                    user_dirs.setup_user_dirs(cfg)
                    dotfiles.setup_dotfiles(cfg)
                    dotfiles.setup_bluetooth(cfg)
                    system_config.apply_static_hosts(cfg)
                    aur.install_aur_helper(cfg)
                    aur.install_aur_packages(cfg)
                    themes.install_themes(cfg)
                    system_config.configure_citrix(cfg)
                    gnome.setup_gnome(cfg)
                    hyprland.setup_hyprland(cfg)
                    features.run_enabled_features(cfg)

                print(f"   {_c('✓', '32')} profile '{p}' simulated prereboot, postreboot, and features cleanly")
            except Exception as e:
                print(f"   {_c('✗', '31')} profile '{p}' failed dry-run simulation: {type(e).__name__}: {e}")
                traceback.print_exc(file=sys.stdout)
                all_ok = False
    finally:
        set_mock_runner(None)
        logging.disable(prev_level)

    return all_ok


def main():
    args = sys.argv[1:]
    mode = "test"
    target_profile = None

    if args:
        if args[0] in ("check", "validate"):
            mode = "check"
            target_profile = args[1] if len(args) > 1 else (detect_profile() or "laptop")
        elif args[0] in ("test", "all"):
            mode = "test"
        else:
            # Assume profile name passed to check
            mode = "check"
            target_profile = args[0]

    print(_c("========================================================", "1;34"))
    if mode == "check":
        print(_c(f" ARCH INSTALL CONFIG CHECK: {target_profile}", "1;36"))
    else:
        print(_c(" ARCH INSTALL PROJECT HEALTH & SANITY TESTS", "1;36"))
    print(_c("========================================================\n", "1;34"))

    if mode == "check":
        ok1 = test_package_profiles()
        ok2 = test_profiles(target_profile)
        ok3 = test_dry_run(target_profile)
        success = ok1 and ok2 and ok3
    else:
        ok1 = test_compile()
        ok2 = test_features()
        ok3 = test_package_profiles()
        ok4 = test_profiles()
        ok5 = test_dry_run()
        success = ok1 and ok2 and ok3 and ok4 and ok5

    print(_c("\n========================================================", "1;34"))
    if success:
        print(_c(" RESULT: ALL CHECKS PASSED ✓", "1;32"))
    else:
        print(_c(" RESULT: ONE OR MORE CHECKS FAILED ✗", "1;31"))
    print(_c("========================================================\n", "1;34"))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

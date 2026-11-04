#!/usr/bin/env python3
# scripts/test_project.py
# Automated test runner and dry-run config validator for arch_install.
# Usage:
#   ./arch-install test              Run all project health and sanity tests
#   ./arch-install check [profile]   Dry-run validate configuration for a profile

import compileall
import importlib
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from core.config import _discover_profiles, load_profile_config, load_yaml, detect_profile
from core.validator import validate

USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _c(text, color_code):
    return f"\033[{color_code}m{text}\033[0m" if USE_COLOR else text


def test_compile():
    print(_c("1. Testing Python compilation...", "1;33"))
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
            # Inject placeholder secrets for non-interactive dry-run validation
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
        success = ok1 and ok2
    else:
        ok1 = test_compile()
        ok2 = test_features()
        ok3 = test_package_profiles()
        ok4 = test_profiles()
        success = ok1 and ok2 and ok3 and ok4

    print(_c("\n========================================================", "1;34"))
    if success:
        print(_c(" RESULT: ALL CHECKS PASSED ✓", "1;32"))
    else:
        print(_c(" RESULT: ONE OR MORE CHECKS FAILED ✗", "1;31"))
    print(_c("========================================================\n", "1;34"))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

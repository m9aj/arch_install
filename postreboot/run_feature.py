# postreboot/run_feature.py
# Standalone feature runner — installs and configures a single named feature.
# Usage: ./arch-install feature <name> [profile]

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import importlib

from core.helper_core import get_config_path, load_profile_config, LOGS_DIR
from core.logger import logger, setup as setup_logger
from core.helper_basic import set_stderr_log
from core.helper_installer import install_packages


def main():
    if os.getuid() == 0:
        print("[ERROR] feature-install must NOT be run as root. Run as your regular user.")
        sys.exit(1)

    # First positional arg is the feature name; remaining args passed to get_config_path via sys.argv
    if len(sys.argv) < 2:
        print("Usage: arch-install feature <feature-name> [profile]")
        sys.exit(1)

    feature_name = sys.argv[1]
    # Shift so get_config_path sees only the profile arg (if any)
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    setup_logger(os.path.join(LOGS_DIR, "features.log"))
    set_stderr_log(os.path.join(LOGS_DIR, "features_err.log"))

    config_path = get_config_path()
    config = load_profile_config(config_path)
    logger.info(f"Using config: {config_path}")

    try:
        module = importlib.import_module(f"features.{feature_name}")
    except ImportError:
        print(f"[ERROR] No feature module found: features/{feature_name}.py")
        sys.exit(1)

    pacman_pkgs = getattr(module, "PACMAN_PACKAGES", [])
    aur_pkgs = getattr(module, "AUR_PACKAGES", [])

    if pacman_pkgs or aur_pkgs:
        logger.info(f"[{feature_name}] Installing packages")
        install_packages(config, pacman_pkgs=pacman_pkgs, aur_pkgs=aur_pkgs)

    feature_cfg = config.get("features", {}).get(feature_name, {})

    if hasattr(module, "configure"):
        logger.info(f"[{feature_name}] Running configure()")
        module.configure(config, feature_cfg)
    else:
        logger.info(f"[{feature_name}] No configure() function — packages only")

    logger.info(f"[{feature_name}] Done.")


if __name__ == "__main__":
    main()

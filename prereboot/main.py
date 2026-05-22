# preinstall/main.py
# Phase 1 — run from Arch live ISO as root.

import sys
import os
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_core import get_config_path, load_profile_config, load_wifi_bootstrap, LOGS_DIR
from core.helper_basic import run
from core.logger import logger, setup as setup_logger, set_stderr_log

from core.validator import validate
from core.state import is_done, mark_done
from core.helper_network import ensure_internet

from prereboot import disk, archinstall, system, bootloader


STEPS = [
    ("disk",       disk.clean_root),
    ("mount",      disk.mount_tree),
    ("pacstrap",   archinstall.install_core),
    ("fstab",      archinstall.generate_fstab),
    ("config",     archinstall.initial_config),
    ("tweaks",     archinstall.initial_tweaks),
    ("packages",   system.install_post),
    ("services",   system.enable_services),
    ("bootloader", bootloader.install_bootloader),
]


def main():
    profile = get_config_path()

    setup_logger(os.path.join(LOGS_DIR, "prereboot.log"))
    set_stderr_log(os.path.join(LOGS_DIR, "prereboot_err.log"))
    logger.info(f"Using profile: {profile}")

    # Connect using unencrypted wifi.yaml before age is available.
    wifi_cfg = load_wifi_bootstrap()
    ensure_internet(wifi_cfg, try_wifi=True)

    # Install age on the live ISO so encrypted secrets can be decrypted.
    if not shutil.which("age"):
        logger.info("Installing age on live ISO")
        run("pacman -Sy --noconfirm age")

    config = load_profile_config(profile)
    validate(config)

    for name, func in STEPS:
        if not is_done(name):
            logger.info(f"Running step: {name}")
            func(config)
            mark_done(name)
        else:
            logger.info(f"Skipping {name}, already done")


if __name__ == "__main__":
    main()

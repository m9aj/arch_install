# features/plymouth.py
# Installs plymouth and sets the boot splash theme.

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_basic import run, apply_kernel_parameter
from core.logger import logger

PACMAN_PACKAGES = ["plymouth"]
SERVICES = []
KERNEL_PARAMS = ["quiet", "splash"]
HOOKS = ["plymouth"]

def configure(config, feature):
    cfg = feature.get("config", {})
    theme = cfg.get("theme", "spinner")
    init = config.get("boot", {}).get("init", "mkinitcpio")

    # Persistent Kernel Parameters in bootloader
    for param in KERNEL_PARAMS:
        apply_kernel_parameter(config, param)

    if init == "mkinitcpio":
        # Inject hooks
        for hook in HOOKS:
            check_cmd = f"sudo grep -q ' {hook} ' /etc/mkinitcpio.conf"
            if run(f"{check_cmd}", check=False).returncode != 0:
                run(f"sudo sed -i 's/ udev / udev {hook} /' /etc/mkinitcpio.conf")

        # -R regenerates the initramfs after setting the theme.
        run(f"sudo plymouth-set-default-theme -R {theme}")
    else:
        logger.warning(f"Plymouth: init={init!r} does not support automatic hook injection — theme set only")
        run(f"sudo plymouth-set-default-theme {theme}")

    if SERVICES:
        logger.info(f"[plymouth] Enabling services: {', '.join(SERVICES)}")
        for svc in SERVICES:
            run(f"sudo systemctl enable --now {svc}")

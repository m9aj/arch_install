# features/plymouth.py
# Installs plymouth and sets the boot splash theme.

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.shell import run, apply_kernel_parameter
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
        # Check whether systemd or udev is used in /etc/mkinitcpio.conf HOOKS
        mk_conf = "/etc/mkinitcpio.conf"
        has_sd_plymouth = run(f"sudo grep -q 'sd-plymouth' {mk_conf}", check=False).returncode == 0
        has_plymouth = run(f"sudo grep -q ' plymouth ' {mk_conf}", check=False).returncode == 0

        if not has_sd_plymouth and not has_plymouth:
            if run(f"sudo grep -q ' systemd ' {mk_conf}", check=False).returncode == 0:
                logger.info("[plymouth] Injecting sd-plymouth hook after systemd in /etc/mkinitcpio.conf")
                run(f"sudo sed -i 's/ systemd / systemd sd-plymouth /' {mk_conf}")
            elif run(f"sudo grep -q ' udev ' {mk_conf}", check=False).returncode == 0:
                logger.info("[plymouth] Injecting plymouth hook after udev in /etc/mkinitcpio.conf")
                run(f"sudo sed -i 's/ udev / udev plymouth /' {mk_conf}")

        # -R regenerates the initramfs after setting the theme.
        run(f"sudo plymouth-set-default-theme -R {theme}")
    else:
        logger.warning(f"Plymouth: init={init!r} does not support automatic hook injection — theme set only")
        run(f"sudo plymouth-set-default-theme {theme}")

    if SERVICES:
        logger.info(f"[plymouth] Enabling services: {', '.join(SERVICES)}")
        for svc in SERVICES:
            run(f"sudo systemctl enable --now {svc}")

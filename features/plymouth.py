# features/plymouth.py
# Installs plymouth and sets the boot splash theme.

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.shell import run, apply_kernel_parameter, rebuild_uki
from core.logger import logger
import shlex

PACMAN_PACKAGES = ["plymouth"]
SERVICES = []
KERNEL_PARAMS = ["quiet", "splash"]
HOOKS = ["plymouth"]

def configure(config, feature):
    cfg = feature.get("config", {})
    theme = cfg.get("theme", "spinner")
    init = config.get("boot", {}).get("init", "mkinitcpio")

    # 1. Set Plymouth theme first so initramfs generation picks it up
    logger.info(f"[plymouth] Setting default theme to '{theme}'")
    run(f"sudo plymouth-set-default-theme {shlex.quote(theme)}")

    # 2. Configure initramfs generator (mkinitcpio or dracut)
    if init == "mkinitcpio":
        mk_conf = "/etc/mkinitcpio.conf"

        # Migrate obsolete sd-plymouth hook if present
        if run(f"sudo grep -q 'sd-plymouth' {mk_conf}", check=False).returncode == 0:
            logger.info("[plymouth] Replacing obsolete sd-plymouth with plymouth in /etc/mkinitcpio.conf")
            run(f"sudo sed -i 's/sd-plymouth/plymouth/g' {mk_conf}")

        has_plymouth = run(f"sudo grep -qE '(\\s|^)plymouth(\\s|$)' {mk_conf}", check=False).returncode == 0

        if not has_plymouth:
            if run(f"sudo grep -q ' systemd ' {mk_conf}", check=False).returncode == 0:
                logger.info("[plymouth] Injecting plymouth hook after systemd in /etc/mkinitcpio.conf")
                run(f"sudo sed -i 's/ systemd / systemd plymouth /' {mk_conf}")
            elif run(f"sudo grep -q ' udev ' {mk_conf}", check=False).returncode == 0:
                logger.info("[plymouth] Injecting plymouth hook after udev in /etc/mkinitcpio.conf")
                run(f"sudo sed -i 's/ udev / udev plymouth /' {mk_conf}")
    elif init == "dracut":
        logger.info("[plymouth] Configuring dracut plymouth module in /etc/dracut.conf.d/plymouth.conf")
        run("sudo mkdir -p /etc/dracut.conf.d")
        run("echo 'add_dracutmodules+=\" plymouth \"' | sudo tee /etc/dracut.conf.d/plymouth.conf > /dev/null")
    else:
        logger.warning(f"Plymouth: unsupported init={init!r}")

    # 3. Ensure kernel parameters are in /etc/kernel/cmdline and rebuild UKI once
    for param in KERNEL_PARAMS:
        apply_kernel_parameter(config, param, rebuild=False)
    rebuild_uki(config)

    if SERVICES:
        logger.info(f"[plymouth] Enabling services: {', '.join(SERVICES)}")
        for svc in SERVICES:
            run(f"sudo systemctl enable --now {svc}")


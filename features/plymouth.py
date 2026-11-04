# features/plymouth.py
# Installs plymouth and sets the boot splash theme.

import sys
import os
import re
import shlex
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.shell import run
from core.kernel import apply_kernel_parameter, rebuild_uki
from core.logger import logger

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
        _configure_plymouth_mkinitcpio()
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
        run(f"sudo systemctl enable --now {' '.join(SERVICES)}")


def _configure_plymouth_mkinitcpio():
    mk_conf = "/etc/mkinitcpio.conf"
    res = run(f"sudo cat {mk_conf}", check=False)
    if res.returncode != 0:
        return
    content = res.stdout

    # Migrate obsolete sd-plymouth hook if present
    content = re.sub(r'\bsd-plymouth\b', 'plymouth', content)

    match = re.search(r'^HOOKS=\((.*?)\)', content, re.MULTILINE | re.DOTALL)
    if match:
        hooks = match.group(1).split()
        if "plymouth" not in hooks:
            logger.info("[plymouth] Injecting plymouth hook into /etc/mkinitcpio.conf HOOKS")
            if "systemd" in hooks:
                idx = hooks.index("systemd") + 1
                hooks.insert(idx, "plymouth")
            elif "udev" in hooks:
                idx = hooks.index("udev") + 1
                hooks.insert(idx, "plymouth")
            else:
                hooks.append("plymouth")

            new_hooks = " ".join(hooks)
            span = match.span(1)
            content = content[:span[0]] + new_hooks + content[span[1]:]
            run(f"sudo tee {mk_conf} > /dev/null", input_data=content, log_cmd=False)
    else:
        logger.warning(f"Could not parse HOOKS in {mk_conf}")


# features/zram.py
# Configures zram swap via zram-generator and tunes vm sysctl knobs.

import sys
import os
import shlex
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_basic import run
from core.logger import logger

PACMAN_PACKAGES = ["zram-generator"]
AUR_PACKAGES = []
SERVICES = []

# Persistent kernel parameters applied to the bootloader in Phase 2
KERNEL_PARAMS = ["zswap.enabled=0"]

def configure(config, feature):
    # Disable zswap for current session
    run("echo 0 | sudo tee /sys/module/zswap/parameters/enabled")

    # Persistent Kernel Parameters in bootloader (systemd-boot)
    boot_mount = config.get("boot", {}).get("boot_mount", "/boot")
    boot_entry = f"{boot_mount}/loader/entries/arch.conf"
    if os.path.exists(boot_entry):
        logger.info(f"[zram] Updating {boot_entry} with kernel parameters")
        for param in KERNEL_PARAMS:
            check_cmd = f"grep -q '{param}' {boot_entry}"
            if run(f"{check_cmd}", check=False).returncode != 0:
                # Append it to the end of the options line
                run(f"sudo sed -i '/^options/ s/$/ {param}/' {boot_entry}")
    else:
        logger.warning(f"[zram] Could not find {boot_entry} to apply kernel parameters")

    cfg = feature.get("config", {})
    size = cfg.get("size", "min(ram / 2, 4096)")
    compression = cfg.get("compression", "zstd")

    run("sudo mkdir -p /etc/systemd/zram-generator.conf.d")
    zram_conf = f"""[zram0]
zram-size = {size}
compression-algorithm = {compression}
"""
    run(f"echo {shlex.quote(zram_conf)} | sudo tee /etc/systemd/zram-generator.conf.d/zram.conf > /dev/null")

    vm_cfg = cfg.get("vm", {})
    if vm_cfg:
        lines = [f"vm.{k} = {v}" for k, v in vm_cfg.items()]
        content = "\n".join(lines)
        run(f"echo {shlex.quote(content)} | sudo tee /etc/sysctl.d/99-vm-zram-parameters.conf > /dev/null")

    if SERVICES:
        run("sudo systemctl daemon-reload")
        logger.info(f"[zram] Enabling services: {', '.join(SERVICES)}")
        for svc in SERVICES:
            run(f"sudo systemctl enable --now {svc}")

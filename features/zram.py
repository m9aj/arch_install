# features/zram.py
# Configures zram swap via zram-generator and tunes vm sysctl knobs.

import sys
import os
import shlex
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.shell import run, apply_kernel_parameter
from core.logger import logger

PACMAN_PACKAGES = ["zram-generator"]
AUR_PACKAGES = []
SERVICES = []

# Persistent kernel parameters applied to the bootloader in Phase 2
KERNEL_PARAMS = ["zswap.enabled=0"]

def configure(config, feature):
    # Disable zswap for current session
    run("echo 0 | sudo tee /sys/module/zswap/parameters/enabled")

    # Persistent Kernel Parameters in bootloader
    for param in KERNEL_PARAMS:
        apply_kernel_parameter(config, param)

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

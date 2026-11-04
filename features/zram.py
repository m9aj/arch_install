# features/zram.py
# Configures zram swap via zram-generator and tunes vm sysctl knobs.

import sys
import os
import shlex
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.shell import run
from core.kernel import apply_kernel_parameter, rebuild_uki
from core.logger import logger

PACMAN_PACKAGES = ["zram-generator"]
AUR_PACKAGES = []
SERVICES = []

# Persistent kernel parameters applied to the bootloader in Phase 2
KERNEL_PARAMS = ["zswap.enabled=0"]

def configure(config, feature):
    # Disable zswap for current session
    if os.path.exists("/sys/module/zswap/parameters/enabled"):
        run("sudo tee /sys/module/zswap/parameters/enabled > /dev/null", input_data="0\n", check=False, log_cmd=False)

    # Persistent Kernel Parameters in bootloader
    for param in KERNEL_PARAMS:
        apply_kernel_parameter(config, param, rebuild=False)
    rebuild_uki(config)

    cfg = feature.get("config", {})
    size = cfg.get("size", "min(ram / 2, 4096)")
    compression = cfg.get("compression", "zstd")

    run("sudo mkdir -p /etc/systemd/zram-generator.conf.d")
    zram_conf = f"""[zram0]
zram-size = {size}
compression-algorithm = {compression}
"""
    run("sudo tee /etc/systemd/zram-generator.conf.d/zram.conf > /dev/null", input_data=zram_conf, log_cmd=False)

    vm_cfg = cfg.get("vm", {})
    if vm_cfg:
        lines = [f"vm.{k} = {v}" for k, v in vm_cfg.items()]
        content = "\n".join(lines) + "\n"
        run("sudo tee /etc/sysctl.d/99-vm-zram-parameters.conf > /dev/null", input_data=content, log_cmd=False)
        logger.info("[zram] Applying VM sysctl parameters live...")
        run("sudo sysctl --system", check=False)

    logger.info("[zram] Reloading systemd and activating zram swap device...")
    run("sudo systemctl daemon-reload")
    run("sudo systemctl restart systemd-zram-setup@zram0.service", check=False)

    if SERVICES:
        logger.info(f"[zram] Enabling services: {', '.join(SERVICES)}")
        run(f"sudo systemctl enable --now {' '.join(SERVICES)}")

# features/btrfs_maintenance.py
# Configures periodic Btrfs maintenance tasks (scrub, balance, trim, defrag)
# using the btrfsmaintenance package.
# Phase: postboot (after first reboot).

import sys
import os
import shlex
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.shell import run
from core.logger import logger

PACMAN_PACKAGES = ["btrfsmaintenance"]
AUR_PACKAGES = []
SERVICES = ["btrfsmaintenance-refresh.path"]


def configure(config, feature):
    cfg = feature.get("config", {})
    scrub_period = cfg.get("scrub_period", "monthly")
    balance_period = cfg.get("balance_period", "monthly")
    defrag_period = cfg.get("defrag_period", "none")
    trim_period = cfg.get("trim_period", "none")

    # Set mountpoints to "auto" so all mounted Btrfs filesystems are maintained
    scrub_mounts = cfg.get("scrub_mountpoints", "auto")
    balance_mounts = cfg.get("balance_mountpoints", "auto")
    defrag_mounts = cfg.get("defrag_mountpoints", "auto")
    trim_mounts = cfg.get("trim_mountpoints", "auto")

    config_path = "/etc/default/btrfsmaintenance"
    if not os.path.exists(config_path):
        logger.error(f"[btrfs_maintenance] Config file {config_path} not found.")
        return

    logger.info("[btrfs_maintenance] Configuring btrfsmaintenance variables...")

    # Read the file
    with open(config_path, "r") as f:
        content = f.read()

    import re
    def set_var(name, val):
        nonlocal content
        pattern = rf'^({name}=)(.*)$'
        replacement = f'\\1"{val}"'
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    # Configure periods
    set_var("BTRFS_SCRUB_PERIOD", scrub_period)
    set_var("BTRFS_BALANCE_PERIOD", balance_period)
    set_var("BTRFS_DEFRAG_PERIOD", defrag_period)
    set_var("BTRFS_TRIM_PERIOD", trim_period)

    # Configure mountpoints to auto-detect all mounted Btrfs filesystems
    set_var("BTRFS_SCRUB_MOUNTPOINTS", scrub_mounts)
    set_var("BTRFS_BALANCE_MOUNTPOINTS", balance_mounts)
    set_var("BTRFS_DEFRAG_MOUNTPOINTS", defrag_mounts)
    set_var("BTRFS_TRIM_MOUNTPOINTS", trim_mounts)

    # Write changes
    run(f"echo {shlex.quote(content)} | sudo tee {config_path} > /dev/null")

    # Start and enable path watcher service
    if SERVICES:
        logger.info(f"[btrfs_maintenance] Enabling services: {', '.join(SERVICES)}")
        for svc in SERVICES:
            run(f"sudo systemctl enable --now {svc}")

    # Restart refresh service once to generate the timers immediately
    logger.info("[btrfs_maintenance] Triggering systemd timer refresh...")
    run("sudo systemctl restart btrfsmaintenance-refresh")

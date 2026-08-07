# features/snapper.py
# Creates a snapper config for root and enables automatic timeline snapshots.
# Phase: postboot (after first reboot).

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.shell import run
from core.logger import logger

PACMAN_PACKAGES = ["snapper"]
SERVICES = ["snapper-timeline.timer", "snapper-cleanup.timer"]


def configure(config, feature):
    cfg = feature.get("config", {})
    target = cfg.get("target", "/mnt/Personal")
    name = cfg.get("name", "Personal")

    if os.path.exists(f"/etc/snapper/configs/{name}"):
        logger.info(f"[snapper] Config '{name}' already exists, skipping create")
    else:
        run(f"sudo snapper -c {name} create-config {target}")

    timeline_limit = cfg.get("timeline_limit_hourly", 5)
    run(f"sudo snapper -c {name} set-config TIMELINE_LIMIT_HOURLY={timeline_limit}")

    timeline_daily = cfg.get("timeline_limit_daily", 7)
    run(f"sudo snapper -c {name} set-config TIMELINE_LIMIT_DAILY={timeline_daily}")

    if SERVICES:
        logger.info(f"[snapper] Enabling services: {', '.join(SERVICES)}")
        for svc in SERVICES:
            run(f"sudo systemctl enable --now {svc}")

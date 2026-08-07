# features/tailscale.py
# Installs tailscale and brings up the VPN.
# Phase: postboot (after first reboot).

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.shell import run
from core.logger import logger

PACMAN_PACKAGES = ["tailscale"]
SERVICES = ["tailscaled"]


def configure(config, feature):
    cfg = feature.get("config", {})

    if SERVICES:
        logger.info(f"[tailscale] Enabling services: {', '.join(SERVICES)}")
        for svc in SERVICES:
            run(f"sudo systemctl enable --now {svc}")

    if cfg.get("auto_up"):
        authkey = config.get("secrets", {}).get("tailscale_authkey") or cfg.get("authkey")
        if authkey:
            logger.info("[tailscale] Authenticating with authkey...")
            run(f"sudo tailscale up --authkey={authkey} || true")
        else:
            logger.info("[tailscale] Running tailscale up with 5s timeout to prevent hanging...")
            run("sudo tailscale up --timeout=5s || true", check=False)

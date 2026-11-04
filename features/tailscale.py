# features/tailscale.py
# Installs tailscale and brings up the VPN.
# Phase: postboot (after first reboot).

import sys
import os
import shlex
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.shell import run
from core.logger import logger

PACMAN_PACKAGES = ["tailscale"]
SERVICES = ["tailscaled"]


def configure(config, feature):
    cfg = feature.get("config", {})

    if SERVICES:
        logger.info(f"[tailscale] Enabling services: {', '.join(SERVICES)}")
        run(f"sudo systemctl enable --now {' '.join(SERVICES)}")

    if cfg.get("auto_up"):
        # Give tailscaled a moment to finish its initial control-plane handshake
        # and load any existing state from /var/lib/tailscale before calling 'tailscale up'.
        time.sleep(3)
        user = config.get("system", {}).get("username")
        up_cmd = f"sudo tailscale up --operator={shlex.quote(user)} 2>&1" if user else "sudo tailscale up 2>&1"
        logger.info("[tailscale] Bringing up Tailscale (authenticate via URL if prompted)...")
        run(up_cmd, check=False)

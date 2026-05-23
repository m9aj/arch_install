# features/pia.py
# Configures Private Internet Access VPN via WireGuard using the official pia-foss/manual-connections scripts.
# Phase: postboot (after first reboot).

import sys
import os
import shlex
import tempfile
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_basic import run
from core.logger import logger

PACMAN_PACKAGES = ["wireguard-tools", "curl", "jq", "git", "openresolv"]
AUR_PACKAGES = []
SERVICES = ["wg-quick@pia"]


def configure(config, feature):
    cfg = feature.get("config", {})

    username = cfg.get("username")
    password = cfg.get("password")

    if not username or not password:
        logger.warning("[pia] Missing username or password in config, skipping")
        return False

    # Create a temporary directory to clone the official scripts
    temp_dir = tempfile.mkdtemp(prefix="pia-setup-")
    try:
        logger.info("[pia] Cloning official pia-foss/manual-connections scripts")
        run(f"git clone --depth 1 https://github.com/pia-foss/manual-connections.git {shlex.quote(temp_dir)}")

        # Format region input
        hosts = cfg.get("hosts", "")
        if hosts:
            preferred_region = hosts.lower().replace(" ", "_")
            autoconnect = "false"
        else:
            preferred_region = ""
            autoconnect = "true"

        # Build connection setup environment variables
        setup_env = {
            "PIA_USER": username,
            "PIA_PASS": password,
            "VPN_PROTOCOL": "wireguard",
            "PREFERRED_REGION": preferred_region,
            "AUTOCONNECT": autoconnect,
            "PIA_CONNECT": "false",
            "PIA_PF": "false",
        }

        # Run the setup script with environment variables, avoiding CLI leakage
        cmd = f"cd {shlex.quote(temp_dir)} && sudo -E ./run_setup.sh 2>&1"
        logger.info(f"[pia] Running setup script to configure WireGuard (region: {preferred_region or 'auto'})")
        run(cmd, env=setup_env, log_cmd=False)

        # Enable and start the systemd service for wg-quick
        if SERVICES:
            logger.info(f"[pia] Enabling services: {', '.join(SERVICES)}")
            for svc in SERVICES:
                run(f"sudo systemctl enable --now {svc}")

    finally:
        # Clean up temp folder
        shutil.rmtree(temp_dir, ignore_errors=True)

    logger.info("[pia] Private Internet Access WireGuard configuration complete")
    return True

# features/pia.py
# Configures Private Internet Access VPN via NetworkManager.
# Phase: postboot (after first reboot).

import sys
import os
import shlex
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_basic import run
from core.logger import logger

PACMAN_PACKAGES = ["networkmanager-openvpn"]
AUR_PACKAGES = ["private-internet-access-vpn"]
SERVICES = ["NetworkManager"]


def configure(config, feature):
    cfg = feature.get("config", {})

    username = cfg.get("username")
    password = cfg.get("password")

    if not username or not password:
        logger.warning("[pia] Missing username or password in config, skipping")
        return False

    login_content = f"{username}\n{password}\n"
    run(f"echo {shlex.quote(login_content)} | sudo tee /etc/private-internet-access/login.conf")
    run("sudo chmod 600 /etc/private-internet-access/login.conf")
    run("sudo chown root:root /etc/private-internet-access/login.conf")

    pia_lines = [
        "[pia]",
        f"openvpn_auto_login = {str(cfg.get('openvpn_auto_login', True))}",
        "",
        "[configure]",
        f"apps = {cfg.get('apps', 'nm')}",
        f"hosts = {cfg.get('hosts', '')}",
        f"port = {cfg.get('port', 1198)}",
    ]
    content = "\n".join(pia_lines)
    run(f"echo {shlex.quote(content)} | sudo tee /etc/private-internet-access/pia.conf")

    if SERVICES:
        logger.info(f"[pia] Enabling services: {', '.join(SERVICES)}")
        for svc in SERVICES:
            run(f"sudo systemctl restart {svc}")

    run("sudo pia -a || true")

# features/firewall.py
# Installs and enables firewalld.
# No extra config — packages and service are handled by resolve_system.
# Phase: preboot (live ISO).

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.shell import run
from core.logger import logger

PACMAN_PACKAGES = ["firewalld"]
SERVICES = ["firewalld"]


def configure(config, feature):
    if SERVICES:
        logger.info(f"[firewall] Enabling services: {', '.join(SERVICES)}")
        for svc in SERVICES:
            run(f"sudo systemctl enable --now {svc}")

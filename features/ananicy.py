# features/ananicy.py
# Installs and enables ananicy-cpp for improved desktop/application responsiveness.
# Phase: postboot (after first reboot).

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.shell import run
from core.logger import logger

PACMAN_PACKAGES = ["ananicy-cpp"]
AUR_PACKAGES = []
SERVICES = ["ananicy-cpp"]


def configure(config, feature):
    if SERVICES:
        logger.info(f"[ananicy] Enabling services: {', '.join(SERVICES)}")
        for svc in SERVICES:
            run(f"sudo systemctl enable --now {svc}")

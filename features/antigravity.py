# features/antigravity.py
# Installs Antigravity CLI via the official installer script.
# Phase: postboot (after first reboot).

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_basic import run
from core.logger import logger

PACMAN_PACKAGES = ["curl"]


def configure(config, feature):
    logger.info("[antigravity] Installing Antigravity CLI")
    run("curl -fsSL https://antigravity.google/cli/install.sh | bash")

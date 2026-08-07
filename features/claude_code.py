# features/claude_code.py
# Installs Claude Code via the official installer script.
# Phase: postboot (after first reboot).

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.shell import run
from core.logger import logger

PACMAN_PACKAGES = ["curl"]


def configure(config, feature):
    logger.info("[claude_code] Installing Claude Code")
    run("curl -fsSL https://claude.ai/install.sh | bash")

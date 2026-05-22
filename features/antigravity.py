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

    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp(prefix="antigravity-install-")
    script_path = os.path.join(temp_dir, "install.sh")
    try:
        # Download the official installer script
        run(f"curl -fsSL https://antigravity.google/cli/install.sh -o {script_path}")

        logger.info("[antigravity] Patching installer script to skip shell profile PATH modification")
        with open(script_path, "r") as f:
            content = f.read()
        # Replace the installer's native agy install calls with --skip-path
        content = content.replace('"$BINARY_PATH" install', '"$BINARY_PATH" install --skip-path')
        with open(script_path, "w") as f:
            f.write(content)

        # Run the installer script
        run(f"bash {script_path}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# features/webapps.py
# Installs firefoxpwa and updates/recreates desktop entries for all restored PWAs.
# Phase: postboot (after first reboot).

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.shell import run
from core.logger import logger

PACMAN_PACKAGES = ["firefoxpwa", "jq"]


def configure(config, feature):
    logger.info("[webapps] Re-registering existing Firefox PWAs and regenerating desktop files...")
    
    res = run("firefoxpwa profile list", check=False)
    if res.returncode != 0 or not res.stdout:
        logger.info("[webapps] firefoxpwa is not available. Skipping registration.")
        return

    import re
    app_ids = re.findall(r'\(([0-9A-Z]{26})\)', res.stdout)
    for app_id in app_ids:
        logger.info(f"[webapps] Re-registering PWA app: {app_id}")
        run(f"firefoxpwa site update {app_id}", check=False)

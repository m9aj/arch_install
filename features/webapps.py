# features/webapps.py
# Installs firefoxpwa and updates/recreates desktop entries for all restored PWAs.
# Phase: postboot (after first reboot).

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_basic import run
from core.logger import logger

PACMAN_PACKAGES = ["firefoxpwa", "jq"]


def configure(config, feature):
    logger.info("[webapps] Re-registering existing Firefox PWAs and regenerating desktop files...")
    
    # Run the shell script to list profiles/apps via firefoxpwa CLI and update each app to recreate launcher entries.
    cmd = (
        "if command -v firefoxpwa &>/dev/null && command -v jq &>/dev/null; then "
        "  firefoxpwa profile list --json | jq -r '.[].apps[].id' 2>/dev/null | while read -r id; do "
        "    logger.info \"[webapps] Re-registering PWA app: $id\"; "
        "    firefoxpwa site update \"$id\" || true; "
        "  done; "
        "else "
        "  echo \"[webapps] firefoxpwa or jq is not available. Skipping registration.\"; "
        "fi"
    )
    # Since logger.info might not be available directly inside the bash shell unless we echo it,
    # let's change `logger.info` inside the shell command to `echo` so it gets printed and drained by the helper_basic.run stdout drainer.
    cmd = (
        "if command -v firefoxpwa &>/dev/null && command -v jq &>/dev/null; then "
        "  firefoxpwa profile list --json | jq -r '.[].apps[].id' 2>/dev/null | while read -r id; do "
        "    echo \"[webapps] Re-registering PWA app: $id\"; "
        "    firefoxpwa site update \"$id\" || true; "
        "  done; "
        "else "
        "  echo \"[webapps] firefoxpwa or jq is not available. Skipping registration.\"; "
        "fi"
    )
    run(cmd)

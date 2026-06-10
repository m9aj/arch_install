# features/gsconnect.py
# Installs GSConnect GNOME extension and adds firewall exceptions.
# Phase: postboot (after first reboot).

import sys
import os
import shutil
import ast
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_basic import run
from core.logger import logger

PACMAN_PACKAGES = []
AUR_PACKAGES = ["gnome-shell-extension-gsconnect"]
SERVICES = []


def configure(config, feature):
    # 1. Enable firewall exception for kdeconnect (used by GSConnect)
    if shutil.which("firewall-cmd"):
        logger.info("[gsconnect] Configuring firewalld exceptions for GSConnect (kdeconnect service)")
        # Add the kdeconnect service permanently
        run("sudo firewall-cmd --permanent --zone=public --add-service=kdeconnect", check=False)
        # Reload the firewall if it is active/running
        res = run("sudo firewall-cmd --state", check=False)
        if res.returncode == 0:
            run("sudo firewall-cmd --reload", check=False)
    else:
        logger.warning("[gsconnect] firewall-cmd not found, skipping firewall configuration")

    # 2. Enable the GNOME Shell extension for the user
    from core.helper_gnome import _is_gnome
    if _is_gnome(config):
        logger.info("[gsconnect] Pre-enabling GSConnect GNOME extension via gsettings")
        uuid = "gsconnect@andyholmes.github.io"
        
        # Read current enabled extensions
        res = run("gsettings get org.gnome.shell enabled-extensions", check=False)
        if res.returncode == 0:
            current_str = res.stdout.strip()
            try:
                if current_str.startswith("@as") or not current_str or current_str == "[]":
                    current_list = []
                else:
                    # Parse the GVariant/python list
                    current_list = ast.literal_eval(current_str)
            except Exception as e:
                logger.warning(f"[gsconnect] Failed to parse current enabled-extensions: {e}")
                current_list = []

            if uuid not in current_list:
                current_list.append(uuid)
                new_str = "[" + ", ".join(f"'{x}'" for x in current_list) + "]"
                logger.info(f"[gsconnect] Setting enabled-extensions to: {new_str}")
                run(f"gsettings set org.gnome.shell enabled-extensions \"{new_str}\"", check=False)
        else:
            logger.warning("[gsconnect] Failed to query current enabled extensions via gsettings")

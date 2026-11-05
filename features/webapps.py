# features/webapps.py
# Installs firefoxpwa and updates/recreates desktop entries for all restored PWAs.
# Phase: postboot (after first reboot).

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.logger import logger
from core.shell import run

PACMAN_PACKAGES = ["firefoxpwa"]

# Custom titlebar theming for individual PWAs: {app_id: (bg_hex, text_hex)}
PWA_THEMES = {
    "01KYKCWQYKGQ5NT68W2FC88V2Q": ("#25D366", "#111b21"),  # WhatsApp (Lime)
    "01KYKD71MMBSANDW29ZQ3GK6PE": ("#38bdf8", "#0f172a"),  # Google Messages (Sky Blue)
}


def apply_pwa_theme(profile_dir: str, bg_color: str, text_color: str):
    """Deploy custom userChrome.css and user.js into a PWA's isolated profile."""
    if not os.path.isdir(profile_dir):
        return

    chrome_dir = os.path.join(profile_dir, "chrome")
    os.makedirs(chrome_dir, exist_ok=True)

    css_path = os.path.join(chrome_dir, "userChrome.css")
    css_content = f"""/* Custom PWA Titlebar Theme */
:root {{
  --pwa-titlebar-bg: {bg_color};
  --pwa-titlebar-color: {text_color};
}}

#navigator-toolbox,
#TabsToolbar {{
  background-color: var(--pwa-titlebar-bg) !important;
  background-image: none !important;
  color: var(--pwa-titlebar-color) !important;
}}

.site-info,
.site-info-title,
#TabsToolbar-customization-target,
.titlebar-buttonbox {{
  color: var(--pwa-titlebar-color) !important;
  fill: currentColor !important;
}}
"""
    try:
        with open(css_path, "w", encoding="utf-8") as f:
            f.write(css_content)
    except OSError as e:
        logger.warning(f"[webapps] Failed to write userChrome.css to {css_path}: {e}")

    user_js = os.path.join(profile_dir, "user.js")
    user_js_lines = [
        'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);\n',
        'user_pref("firefoxpwa.dynamicThemeColor", false);\n',
    ]
    try:
        with open(user_js, "w", encoding="utf-8") as f:
            f.writelines(user_js_lines)
    except OSError as e:
        logger.warning(f"[webapps] Failed to write user.js to {user_js}: {e}")


def configure(config, feature):
    logger.info("[webapps] Re-registering existing Firefox PWAs and regenerating desktop files...")
    
    res = run("firefoxpwa profile list", check=False)
    if res.returncode != 0 or not res.stdout:
        logger.info("[webapps] firefoxpwa is not available. Skipping registration.")
        return

    app_ids = re.findall(r'\(([0-9A-Z]{26})\)', res.stdout)
    for app_id in app_ids:
        logger.info(f"[webapps] Re-registering PWA app: {app_id}")
        run(f"firefoxpwa site update {app_id}", check=False)

    # Apply per-PWA custom themes to their respective profile directories
    config_file = os.path.expanduser("~/.local/share/firefoxpwa/config.json")
    if os.path.isfile(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            sites = cfg.get("sites", {})
            profiles_root = os.path.expanduser("~/.local/share/firefoxpwa/profiles")
            for app_id, (bg, text) in PWA_THEMES.items():
                site = sites.get(app_id)
                if site and site.get("profile"):
                    prof_dir = os.path.join(profiles_root, site["profile"])
                    logger.info(f"[webapps] Applying theme ({bg}) to PWA {app_id} in {prof_dir}")
                    apply_pwa_theme(prof_dir, bg, text)
        except Exception as e:
            logger.warning(f"[webapps] Failed to apply custom PWA themes: {e}")


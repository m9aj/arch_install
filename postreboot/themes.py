# postreboot/themes.py
# Installs icon/cursor themes from local zip archives and downloads wallpapers.

import os
import shlex
import tempfile
from core.config import PROJECT_ROOT
from core.shell import run
from core.logger import logger
from core.gnome import _is_gnome


def _resolve(source):
    return source if os.path.isabs(source) else os.path.join(PROJECT_ROOT, source)


def install_icons(config):
    cfg = config.get("postconfig", {}).get("gnome", {}).get("theme", {}).get("icons", {})
    if not cfg.get("enabled"):
        return

    source = _resolve(cfg["source"])
    name = cfg["name"]
    user = config["system"]["username"]
    icons_dir = f"/home/{user}/.local/share/icons"

    if not os.path.exists(source):
        logger.warning(f"[THEME] Icon archive not found: {source}")
        return

    logger.info(f"[THEME] Installing icon theme: {name}")
    run(f"mkdir -p {icons_dir}")
    run(f"unzip -o '{source}' -d {icons_dir}")
    run(f"gtk-update-icon-cache -f {icons_dir}/{name}/")
    
    if _is_gnome(config):
        run(f"gsettings set org.gnome.desktop.interface icon-theme '{name}'")


def install_cursors(config):
    cfg = config.get("postconfig", {}).get("gnome", {}).get("theme", {}).get("cursor", {})
    if not cfg.get("enabled"):
        return

    source = _resolve(cfg["source"])
    name = cfg["name"]
    user = config["system"]["username"]
    icons_dir = f"/home/{user}/.local/share/icons"

    if not os.path.exists(source):
        logger.warning(f"[THEME] Cursor archive not found: {source}")
        return

    logger.info(f"[THEME] Installing cursor theme: {name}")
    run(f"mkdir -p {icons_dir}")
    run(f"unzip -o '{source}' -d {icons_dir}")
    
    if _is_gnome(config):
        run(f"gsettings set org.gnome.desktop.interface cursor-theme '{name}'")


def install_wallpapers(config):
    cfg = config.get("postconfig", {}).get("gnome", {}).get("theme", {}).get("wallpapers", {})
    if not cfg.get("enabled"):
        return

    user = config["system"]["username"]
    repo = cfg["repo"]
    raw_base = repo.replace("https://github.com/", "https://raw.githubusercontent.com/")
    install_url = f"{raw_base}/main/direct_install.sh"

    logger.info(f"[THEME] Installing wallpapers from {repo}")
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".sh")
    os.close(tmp_fd)
    try:
        run(f"curl -fsSL {shlex.quote(install_url)} -o {shlex.quote(tmp_path)}")
        run(f"bash {shlex.quote(tmp_path)} < /dev/null")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def install_themes(config):
    install_icons(config)
    install_cursors(config)
    install_wallpapers(config)

# postreboot/themes.py
# Installs cursor themes from local zip archives and downloads wallpapers.

import os
import pwd
import shlex
import tempfile
import zipfile
from core.config import PROJECT_ROOT
from core.shell import run
from core.logger import logger
from core.desktop import _is_gnome


def _resolve(source):
    return source if os.path.isabs(source) else os.path.join(PROJECT_ROOT, source)


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
    os.makedirs(icons_dir, exist_ok=True)
    with zipfile.ZipFile(source, "r") as zip_ref:
        zip_ref.extractall(icons_dir)

    try:
        pw = pwd.getpwnam(user)
        for root, dirs, files in os.walk(icons_dir):
            os.chown(root, pw.pw_uid, pw.pw_gid)
            for f in files:
                os.chown(os.path.join(root, f), pw.pw_uid, pw.pw_gid)
    except Exception:
        pass
    
    if _is_gnome(config):
        run(f"gsettings set org.gnome.desktop.interface cursor-theme '{name}'", check=False)


def install_wallpapers(config):
    cfg = config.get("postconfig", {}).get("gnome", {}).get("theme", {}).get("wallpapers", {})
    if not cfg.get("enabled"):
        return

    repo = cfg.get("repo", "").strip()
    if not repo:
        return

    logger.info(f"[THEME] Installing wallpapers from {repo}")
    raw_base = repo.replace("https://github.com/", "https://raw.githubusercontent.com/").rstrip("/")
    install_url = f"{raw_base}/main/Easy_Install.sh"

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
    install_cursors(config)
    install_wallpapers(config)

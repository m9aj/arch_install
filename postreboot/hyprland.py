# postreboot/hyprland.py
# Clones Impasto to a temporary directory, applies patches from assets/hyprland,
# and runs unattended installation.

import os
import shutil
from core.gnome import _is_hyprland
from core.logger import logger
from core.shell import run
from core.config import PROJECT_ROOT


def setup_hyprland(config):
    if not _is_hyprland(config):
        return False

    user = config["system"]["username"]
    assets_dir = os.path.join(PROJECT_ROOT, "assets", "hyprland")
    patcher = os.path.join(assets_dir, "patch-impasto.py")

    if not os.path.exists(patcher):
        logger.warning(f"[HYPRLAND] Impasto patcher not found at {patcher}, skipping setup.")
        return False

    logger.info("[HYPRLAND] Setting up patched Impasto Hyprland environment...")

    build_dir = "/tmp/impasto_build"
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir, exist_ok=True)
    run(f"sudo chown -R {user}:{user} '{build_dir}'")

    try:
        cmd = (
            f"sudo -H -u {user} python3 '{patcher}' "
            f"--repo '{build_dir}' "
            f"--unattended"
        )
        run(cmd)
        logger.info("[HYPRLAND] Impasto installation and patching completed successfully.")
        return True
    finally:
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir, ignore_errors=True)

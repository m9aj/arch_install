# postreboot/hyprland.py
# Clones Impasto to a temporary directory, applies patches from assets/hyprland,
# and runs unattended installation.

import os
import shutil
from core.desktop import _is_hyprland, is_standalone_hyprland
from core.logger import logger
from core.shell import run
from core.config import PROJECT_ROOT


def setup_hyprland(config):
    if not _is_hyprland(config):
        return False

    user = config["system"]["username"]

    # For standalone Hyprland (no GDM), configure TTY1 autologin and autostart
    if is_standalone_hyprland(config):
        logger.info(f"[HYPRLAND] Ensuring TTY1 autologin and Hyprland autostart for {user}")
        run("sudo mkdir -p /etc/systemd/system/getty@tty1.service.d")
        autologin_content = f"""[Service]
ExecStart=
ExecStart=-/sbin/agetty -o '-p -f -- \\\\u' --noclear --autologin {user} %I $TERM
"""
        run("sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf > /dev/null", input_data=autologin_content, log_cmd=False)
        run("sudo systemctl daemon-reload")
        run("sudo systemctl disable gdm 2>/dev/null || true", check=False)

        autostart_content = f"""# Automatically launch Hyprland on TTY1 login for standalone Hyprland
if [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ] && [ "$XDG_VTNR" -eq 1 ] && [ "$(id -un)" = "{user}" ]; then
    exec Hyprland
fi
"""
        run("sudo tee /etc/profile.d/hyprland-autostart.sh > /dev/null", input_data=autostart_content, log_cmd=False)
        run("sudo chmod 755 /etc/profile.d/hyprland-autostart.sh")

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
    import getpass
    curr_user = getpass.getuser()
    if curr_user != user:
        run(f"sudo chown -R {user}:{user} '{build_dir}'")

    prefix = "" if curr_user == user else f"sudo -H -u {user} "
    try:
        cmd = (
            f"{prefix}python3 '{patcher}' "
            f"--repo '{build_dir}' "
            f"--unattended"
        )
        run(cmd)
        logger.info("[HYPRLAND] Impasto installation and patching completed successfully.")
        return True
    finally:
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir, ignore_errors=True)

# postreboot/aur.py

import re
import tempfile
from core.helper_basic import run
from core.logger import logger
from core.helper_installer import install_packages


def install_aur_helper(config):
    helper = config.get("machine_specific", {}).get("aur_helper", "pikaur")

    if helper == "none":
        return

    user = config["system"]["username"]

    if not re.match(r'^[a-zA-Z0-9_-]+$', helper):
        raise ValueError(f"[AUR] Unsafe helper name: {helper}")

    logger.info(f"[AUR] Installing helper: {helper}")

    build_dir = tempfile.mkdtemp(prefix=f"aur_{helper}_")

    # 1. We install dependencies as root via sudo
    # 2. We build the package as the user (makepkg refuses to run as root)
    # 3. We install the resulting package as root via sudo
    cmd = f"""
set -e
sudo pacman -S --needed --noconfirm git base-devel
git clone https://aur.archlinux.org/{helper}.git '{build_dir}/{helper}'
cd '{build_dir}/{helper}'
makepkg -sc --noconfirm
sudo pacman -U --noconfirm *.pkg.tar.zst
sudo rm -rf '{build_dir}'
"""
    run(cmd)


def import_gpg_keys(config):
    keys = config.get("machine_specific", {}).get("gpg_keys", [])
    if not keys:
        return

    user = config["system"]["username"]
    for key in keys:
        if not re.match(r'^[0-9A-Fa-f]{16,40}$', key):
            logger.warning(f"[GPG] Skipping invalid fingerprint: {key}")
            continue
        logger.info(f"[GPG] Importing key: {key}")
        result = run(
            f"sudo -u {user} gpg --keyserver hkps://keyserver.ubuntu.com --recv-keys {key}",
            check=False
        )
        if result.returncode != 0:
            logger.warning(f"[GPG] Failed to import key {key}, AUR builds requiring it may fail")


def install_aur_packages(config):
    """Install non-feature AUR packages defined in machine_specific."""
    pkgs = config.get("machine_specific", {}).get("aur", [])

    if not pkgs:
        return []

    run("sudo pacman -Syy --noconfirm", check=False)
    import_gpg_keys(config)
    helper = config.get("machine_specific", {}).get("aur_helper", "pikaur")
    failed = []
    for pkg in pkgs:
        logger.info(f"[AUR] Installing: {pkg}")
        result = run(f"{helper} -S --noconfirm --needed {pkg}", check=False)
        if result.returncode != 0:
            logger.warning(f"[AUR] Failed to install {pkg} (exit code: {result.returncode}), skipping")
            failed.append(pkg)

    if failed:
        logger.warning(f"[AUR] Skipped packages: {', '.join(failed)}")

    return failed

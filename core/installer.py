# core/helper_installer.py

from core.shell import run
from core.logger import logger
def install_packages(config, pacman_pkgs=None, aur_pkgs=None):
    """
    Helper to install both pacman and AUR packages.
    AUR packages are installed as the user via the configured AUR helper.
    """
    if pacman_pkgs:
        logger.info(f"Installing pacman packages: {', '.join(pacman_pkgs)}")
        run(f"sudo pacman -S --noconfirm --needed {' '.join(pacman_pkgs)}")

    if aur_pkgs:
        helper = config.get("machine_specific", {}).get("aur_helper", "paru")
        logger.info(f"Installing AUR packages: {', '.join(aur_pkgs)}")
        for pkg in aur_pkgs:
            run(f"{helper} -S --noconfirm --needed {pkg}")

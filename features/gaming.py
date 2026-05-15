# features/gaming.py

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_basic import run
from core.helper_installer import install_packages
from core.logger import logger

# Empty — multilib must be enabled before lib32/steam packages can install,
# so configure() owns the full install sequence.
PACMAN_PACKAGES = []
AUR_PACKAGES = []
SERVICES = []

GAMING_PACMAN = [
    "steam",
    "lib32-nvidia-utils",
    "gamemode",
    "lib32-gamemode",
    "mangohud",
    "lib32-mangohud",
]

GAMING_AUR = ["proton-ge-custom"]


def _enable_multilib():
    run(
        "sudo sed -i '/^#\\[multilib\\]/{N;s/^#\\[multilib\\]\\n#Include/[multilib]\\nInclude/}' "
        "/etc/pacman.conf"
    )
    run("sudo pacman -Sy")


def configure(config, feature):
    logger.info("[gaming] Enabling multilib repository")
    _enable_multilib()

    logger.info("[gaming] Installing gaming packages")
    install_packages(config, pacman_pkgs=GAMING_PACMAN, aur_pkgs=GAMING_AUR)

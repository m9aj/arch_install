# preinstall/system.py

from core.shell import chroot
from core.resolver import resolve_system
from core.logger import logger


def install_post(config):
    system = resolve_system(config)
    post_pkgs = system.get("post", [])

    if not post_pkgs:
        return

    logger.info("Installing post packages")
    chroot(f"pacman -S --noconfirm --needed {' '.join(post_pkgs)} --overwrite '*'")


def enable_services(config):
    system = resolve_system(config)
    services = system.get("services", [])

    if not services:
        return

    logger.info(f"Enabling services: {', '.join(services)}")
    chroot(f"systemctl enable {' '.join(services)}")


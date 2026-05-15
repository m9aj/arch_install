# features/reflector.py
# Writes reflector.conf and runs an initial mirror sync.
# Phase: preboot (live ISO).

import sys
import os
import shlex
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_basic import run
from core.logger import logger

PACMAN_PACKAGES = ["reflector"]
SERVICES = ["reflector.timer"]


def configure(config, feature):
    cfg = feature.get("config", {})

    MIRRORLIST = "/etc/pacman.d/mirrorlist"

    lines = [f"--save {MIRRORLIST}"]  # hardcoded — changing this breaks pacman
    if cfg.get("protocol"):
        lines.append(f"--protocol {cfg['protocol']}")
    if cfg.get("country"):
        lines.append(f"--country '{cfg['country']}'")
    if cfg.get("latest"):
        lines.append(f"--latest {cfg['latest']}")
    if cfg.get("sort"):
        lines.append(f"--sort {cfg['sort']}")
    if cfg.get("age"):
        lines.append(f"--age {cfg['age']}")

    content = "\n".join(lines)
    run("sudo mkdir -p /etc/xdg/reflector")
    run(f"echo {shlex.quote(content)} | sudo tee /etc/xdg/reflector/reflector.conf")
    run("sudo reflector @/etc/xdg/reflector/reflector.conf")

    if SERVICES:
        logger.info(f"[reflector] Enabling services: {', '.join(SERVICES)}")
        for svc in SERVICES:
            run(f"sudo systemctl enable --now {svc}")

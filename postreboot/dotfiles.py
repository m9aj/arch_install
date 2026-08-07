# postreboot/dotfiles.py

import os
from core.shell import run
from core.logger import logger


def setup_dotfiles(config):
    cfg = config.get("postconfig", {}).get("dotfiles", {})

    if not cfg.get("enabled"):
        return

    user = config["system"]["username"]
    home = f"/home/{user}"
    source_dir = cfg.get("source_dir")

    if not source_dir or not os.path.exists(source_dir):
        logger.warning(f"Dotfiles source_dir missing or not found: {source_dir}")
        return

    # Write chezmoi.toml so the source dir is set persistently for future chezmoi calls
    chezmoi_cfg_dir = os.path.join(home, ".config", "chezmoi")
    chezmoi_cfg_file = os.path.join(chezmoi_cfg_dir, "chezmoi.toml")
    if not os.path.exists(chezmoi_cfg_file):
        os.makedirs(chezmoi_cfg_dir, exist_ok=True)
        with open(chezmoi_cfg_file, "w") as f:
            f.write(f'sourceDir = "{source_dir}"\n')
        run(f"chown -R {user}:{user} {chezmoi_cfg_dir}")

    logger.info(f"Applying dotfiles with chezmoi from {source_dir}")
    run(f"sudo -H -u {user} chezmoi apply --source {source_dir}")



def setup_bluetooth(config):
    cfg = config.get("postconfig", {}).get("bluetooth", {})

    if not cfg.get("enabled"):
        return False

    source = cfg.get("source")
    target = "/var/lib/bluetooth"

    if not source or not os.path.exists(source):
        logger.warning(f"Bluetooth source path missing or not found: {source}")
        return

    logger.info("Restoring Bluetooth configuration")

    run(f"sudo mkdir -p {target}")
    # Securely copy contents and preserve attributes, then enforce root ownership
    run(f"sudo cp -aT {source} {target}")
    run(f"sudo chown -R root:root {target}")
    run("sudo systemctl restart bluetooth")

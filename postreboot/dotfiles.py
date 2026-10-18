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

    chezmoi_cfg_dir = os.path.join(home, ".config", "chezmoi")
    os.makedirs(chezmoi_cfg_dir, exist_ok=True)

    # Restore age decryption key from persistent storage if available
    key_backup = os.path.join(os.path.dirname(source_dir), "chezmoi-key.txt")
    target_key = os.path.join(chezmoi_cfg_dir, "key.txt")
    if os.path.exists(key_backup) and not os.path.exists(target_key):
        logger.info("Restoring chezmoi age decryption key from persistent storage")
        run(f"cp '{key_backup}' '{target_key}'")
        run(f"chmod 600 '{target_key}'")

    run(f"chown -R {user}:{user} {chezmoi_cfg_dir}")

    logger.info(f"Initializing and applying dotfiles with chezmoi from {source_dir}")
    run(f"sudo -H -u {user} chezmoi init --source {source_dir}")
    run(f"sudo -H -u {user} chezmoi apply --source {source_dir} --force")



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

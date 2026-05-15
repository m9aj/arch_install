# postreboot/dotfiles.py

import os
import shutil
from core.helper_basic import run
from core.logger import logger


def setup_dotfiles(config):
    cfg = config.get("postconfig", {}).get("dotfiles", {})

    if not cfg.get("enabled"):
        return

    user = config["system"]["username"]
    home = f"/home/{user}"
    dotfiles_dir = cfg.get("path")

    if not dotfiles_dir or not os.path.exists(dotfiles_dir):
        logger.warning(f"Dotfiles path missing or not found: {dotfiles_dir}")
        return

    logger.info("Preparing dotfiles (recursive cleanup)")

    def map_name(name):
        if name.startswith("dot-"):
            return "." + name[4:]
        # Note: GNU Stow --dotfiles ONLY maps 'dot-' prefix.
        # But some users expect forced dotting. We'll stick to 'dot-' mapping.
        return name

    # Recursive walk to find all potential conflicts
    for root, dirs, files in os.walk(dotfiles_dir):
        # Get path relative to dotfiles_dir
        rel_root = os.path.relpath(root, dotfiles_dir)
        if rel_root == ".":
            target_root = home
        else:
            # Map each part of the path
            parts = rel_root.split(os.sep)
            mapped_parts = [map_name(p) for p in parts]
            target_root = os.path.join(home, *mapped_parts)

        # Check for conflicting entries (files and directories)
        # We check both because a file in repo might conflict with a dir in HOME, or vice versa.
        all_entries = dirs + files
        for entry in all_entries:
            target_path = os.path.join(target_root, map_name(entry))
            
            # Use lexists to catch broken symlinks
            if os.path.lexists(target_path) and not os.path.islink(target_path):
                if os.path.isfile(target_path):
                    logger.info(f"Removing conflicting file: {target_path}")
                    os.remove(target_path)
                # Real directories are left intact — stow links files inside them

    run(f"stow --dir {dotfiles_dir} --target {home} --dotfiles .")



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

# postreboot/home_shortcuts.py

import os
import shutil
import pwd
from core.logger import logger


def setup_user_dirs(config):
    cfg = config.get("postconfig", {}).get("user_dirs", {})

    if not cfg.get("enabled"):
        return

    parent = cfg.get("parent")
    folders = cfg.get("folders", [])

    if not parent or not folders:
        logger.warning("user_dirs misconfigured")
        return

    user = config["system"]["username"]
    home = f"/home/{user}"
    
    # Get user UID/GID to fix ownership later
    try:
        pw = pwd.getpwnam(user)
        uid = pw.pw_uid
        gid = pw.pw_gid
    except KeyError:
        logger.error(f"User {user} not found, cannot fix ownership")
        return

    logger.info(f"Setting up user directories for {user}")

    for folder in folders:
        source = os.path.join(parent, folder)
        target = os.path.join(home, folder)

        if not os.path.exists(source):
            logger.warning(f"Missing source: {source}")
            continue

        if os.path.islink(target) or os.path.isfile(target):
            os.unlink(target)
        elif os.path.isdir(target):
            shutil.rmtree(target)

        # Create the symlink
        os.symlink(source, target)
        
        # Fix ownership of the symlink itself (follow_symlinks=False)
        os.chown(target, uid, gid, follow_symlinks=False)

# postreboot/user_dirs.py

import os
import pwd
import shutil
import subprocess
from core.logger import logger
from core.shell import run


def setup_user_dirs(config):
    cfg = config.get("postconfig", {}).get("user_dirs", {})

    if not cfg.get("enabled"):
        return

    parent = cfg.get("parent")
    folders = cfg.get("folders", [])
    method = cfg.get("method", "bind")

    if not parent or not folders:
        logger.warning("user_dirs misconfigured")
        return

    user = config["system"]["username"]
    home = f"/home/{user}"

    # Get user UID/GID to fix ownership
    try:
        pw = pwd.getpwnam(user)
        uid = pw.pw_uid
        gid = pw.pw_gid
    except KeyError:
        logger.error(f"User {user} not found, cannot fix ownership")
        return

    logger.info(f"Setting up user directories for {user} (method: {method})")

    fstab_path = "/etc/fstab"
    fstab_content = ""
    if method == "bind" and os.path.exists(fstab_path):
        with open(fstab_path, "r", encoding="utf-8") as f:
            fstab_content = f.read()

    new_fstab_lines = []

    for folder in folders:
        source = os.path.join(parent, folder)
        target = os.path.join(home, folder)

        if not os.path.exists(source):
            logger.warning(f"Missing source: {source}")
            continue

        if method == "symlink":
            if os.path.islink(target) or os.path.isfile(target):
                os.unlink(target)
            elif os.path.isdir(target) and not os.path.ismount(target):
                shutil.rmtree(target)
            os.symlink(source, target)
            os.chown(target, uid, gid, follow_symlinks=False)
        else:
            # Bind mount method
            if os.path.islink(target) or os.path.isfile(target):
                os.unlink(target)
            os.makedirs(target, exist_ok=True)
            os.chown(target, uid, gid)

            req_mount = "/" + "/".join(parent.strip("/").split("/")[:2])
            entry = f"{source}  {target}  none  bind,nofail,x-gvfs-hide,x-systemd.requires={req_mount}  0 0"
            if f" {target} " not in fstab_content:
                new_fstab_lines.append(entry)

    if method == "bind":
        if new_fstab_lines:
            block = ""
            if "# User Directory Bind Mounts" not in fstab_content:
                block += "\n# User Directory Bind Mounts\n"
            block += "\n".join(new_fstab_lines) + "\n"

            proc = subprocess.run(
                ["sudo", "tee", "-a", fstab_path],
                input=block,
                text=True,
                capture_output=True,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"Failed to append to {fstab_path}: {proc.stderr.strip()}")

            run("sudo systemctl daemon-reload")
        run("sudo mount -a")

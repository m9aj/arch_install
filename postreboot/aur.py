# postreboot/aur.py

import glob
import os
import re
import shlex
import shutil
import tempfile
from core.shell import run
from core.logger import logger

PKG_CACHE_DIR = "/var/cache/pacman/pkg"


def ensure_pkg_cache_permissions():
    """Ensure wheel group can write to /var/cache/pacman/pkg for non-root makepkg builds."""
    run(
        "sudo chown root:wheel /var/cache/pacman/pkg && "
        "sudo chmod 775 /var/cache/pacman/pkg && "
        "sudo chmod g+s /var/cache/pacman/pkg",
        check=False,
    )
    if shutil.which("setfacl"):
        run("sudo setfacl -d -m g:wheel:rwX /var/cache/pacman/pkg 2>/dev/null", check=False)


def find_cached_package(pkg_name):
    """
    Look for a pre-built .pkg.tar.* for pkg_name in the persistent package cache.
    Returns the newest matching file path, or None.
    Arch packages follow the naming convention: <pkgname>-<pkgver>-<pkgrel>-<arch>.pkg.tar.*
    where pkgver starts with a digit.
    """
    if not os.path.isdir(PKG_CACHE_DIR):
        return None

    pattern = os.path.join(PKG_CACHE_DIR, f"{pkg_name}-[0-9]*.pkg.tar.*")
    candidates = glob.glob(pattern)

    valid = []
    prefix = f"{pkg_name}-"
    for path in candidates:
        fname = os.path.basename(path)
        if fname.endswith(".sig"):
            continue
        if fname.startswith(prefix):
            valid.append(path)

    if not valid:
        return None

    valid.sort(key=os.path.getmtime, reverse=True)
    return valid[0]


def install_single_aur_package(config, pkg):
    """
    Install an AUR package cache-first.
    If a matching .pkg.tar.* exists in /var/cache/pacman/pkg, install directly with pacman -U.
    Otherwise, build via the AUR helper (which places the resulting package into PKGDEST).
    """
    ensure_pkg_cache_permissions()
    helper = config.get("machine_specific", {}).get("aur_helper", "paru")

    cached_pkg = find_cached_package(pkg)
    if cached_pkg:
        logger.info(f"[AUR] Installing '{pkg}' from persistent cache: {os.path.basename(cached_pkg)}")
        res = run(f"sudo pacman -U --noconfirm --needed {shlex.quote(cached_pkg)}", check=False)
        if res.returncode == 0:
            return True
        logger.warning(f"[AUR] Failed to install cached package {cached_pkg}, falling back to build via {helper}")

    logger.info(f"[AUR] Installing via {helper}: {pkg}")
    res = run(f"{helper} -S --noconfirm --needed {pkg}", check=False)
    return res.returncode == 0


def install_aur_helper(config):
    helper = config.get("machine_specific", {}).get("aur_helper", "paru")

    if helper == "none":
        return

    if shutil.which(helper):
        logger.info(f"[AUR] Helper '{helper}' is already installed, skipping compilation.")
        return

    ensure_pkg_cache_permissions()

    # Check if helper was already built and cached in persistent storage
    cached_helper = find_cached_package(helper)
    if cached_helper:
        logger.info(f"[AUR] Installing helper '{helper}' from persistent cache: {os.path.basename(cached_helper)}")
        res = run(f"sudo pacman -U --noconfirm {shlex.quote(cached_helper)}", check=False)
        if res.returncode == 0 and shutil.which(helper):
            return
        logger.warning(f"[AUR] Failed to install cached helper {cached_helper}, recompiling from source...")

    user = config["system"]["username"]

    if not re.match(r'^[a-zA-Z0-9_-]+$', helper):
        raise ValueError(f"[AUR] Unsafe helper name: {helper}")

    logger.info(f"[AUR] Installing helper: {helper}")

    build_dir = tempfile.mkdtemp(prefix=f"aur_{helper}_")

    # 1. Install dependencies as root via sudo
    # 2. Build the package as user (makepkg places .pkg.tar.* in PKGDEST=/var/cache/pacman/pkg or current dir)
    # 3. Install resulting package via sudo pacman -U
    cmd = f"""
set -e
sudo pacman -S --needed --noconfirm git base-devel
git clone https://aur.archlinux.org/{helper}.git '{build_dir}/{helper}'
cd '{build_dir}/{helper}'
makepkg -sc --noconfirm
PKG_FILE=$(ls -t {PKG_CACHE_DIR}/{helper}-[0-9]*.pkg.tar.* 2>/dev/null | head -n1 || true)
if [ -z "$PKG_FILE" ]; then
    PKG_FILE=$(ls -t *.pkg.tar.* 2>/dev/null | head -n1 || true)
fi
if [ -n "$PKG_FILE" ]; then
    sudo pacman -U --noconfirm "$PKG_FILE"
fi
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
    failed = []
    for pkg in pkgs:
        success = install_single_aur_package(config, pkg)
        if not success:
            logger.warning(f"[AUR] Failed to install {pkg}, skipping")
            failed.append(pkg)

    if failed:
        logger.warning(f"[AUR] Skipped packages: {', '.join(failed)}")

    return failed

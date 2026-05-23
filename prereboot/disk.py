# preinstall/disk.py

import os
from core.helper_basic import run, confirm
from core.helper_disk import get_partition, get_root_partition
from core.logger import logger

# ------------------------
# Main
# ------------------------

def clean_root(config):
    run("umount -R /mnt || true")
    root_mode = config["root"]["mode"]

    if root_mode == "format":
        logger.info("Formatting root filesystem")
        reformat_root(config)
    elif root_mode == "reuse":
        logger.info("Reusing root filesystem with subvolume control")

    handle_root_subvolumes(config)

def mount_tree(config):
    mount_subvolumes(config)
    mount_efi(config)
    clean_efi(config)

# ------------------------
# Format Root
# ------------------------

def reformat_root(config):
    root_part = get_root_partition(config)
    root_label = config["arch"]["label"]
    confirm(f"This will DELETE all data on {root_part}")

    run(f"mkfs.btrfs -f -L {root_label} {root_part}")

# ------------------------
# Subvolume handling
# ------------------------

def handle_root_subvolumes(config):
    root_part = get_root_partition(config)
    subvols = config["root"].get("subvolumes", [])
    
    run(f"mount -o subvolid=5 {root_part} /mnt")

    try:
        for sv in subvols:
            name = sv["name"]
            reuse_val = sv.get("reuse", "yes")
            path = f"/mnt/{name}"

            # Treat False or "no" as 'don't reuse' (clean contents)
            should_reuse = True
            if isinstance(reuse_val, bool):
                should_reuse = reuse_val
            elif str(reuse_val).lower() == "no":
                should_reuse = False

            # 1. Ensure subvolume exists
            if not os.path.exists(path):
                logger.info(f"Creating subvolume {name}")
                run(f"btrfs subvolume create {path}")

            # 2. If not reusing, empty it (keep the subvolume itself)
            if not should_reuse:
                logger.info(f"Cleaning contents of subvolume {name}")
                run(f"find {path} -mindepth 1 -delete || true")

            # Disable CoW for the log subvolume (@var)
            if name == "@var":
                logger.info(f"Disabling CoW for subvolume {name}")
                run(f"chattr +C {path}")
    finally:
        run("umount /mnt")

# ------------------------
# Mount root and subvolumes
# ------------------------

def mount_subvolumes(config):
    subvols = config["root"]["subvolumes"]
    mount_ops = config["disk"].get("mount_ops_ssd", "")
    root_part = get_root_partition(config)

    for sv in subvols:
        name = sv["name"]
        mount_point = sv.get("mount")
        if not mount_point:
            continue  # override-only entry (machine profile reuse flag without mount path)

        target = f"/mnt{mount_point}"
        os.makedirs(target, exist_ok=True)

        opts = f"subvol={name}"
        if mount_ops:
            opts = f"{opts},{mount_ops}"

        run(f"mount -o {opts} {root_part} {target}")

# ------------------------
# Mount and clean EFI partition
# ------------------------

def mount_efi(config):
    disk = config["disk"]
    device = get_partition(disk["disk_by_id"], disk["boot_part"])
    mount_path = "/efi"
    mountpoint = f"/mnt{mount_path}"

    logger.info(f"Mounting EFI: {device} → {mountpoint}")
    os.makedirs(mountpoint, exist_ok=True)
    run(f"mount {device} {mountpoint}")

def clean_efi(config):
    disk = config["disk"]
    mount_path = "/efi"
    mountpoint = f"/mnt{mount_path}"

    # We always clean old kernels/initramfs and bootloader files from /boot 
    # since the EFI partition itself is never formatted.
    logger.info(f"Cleaning old boot files in {mountpoint}")
    
    # Files
    run(f"rm -f {mountpoint}/vmlinuz-*")
    run(f"rm -f {mountpoint}/*.img")
    
    # Folders
    run(f"rm -rf {mountpoint}/loader")
    run(f"rm -rf {mountpoint}/EFI/BOOT")
    run(f"rm -rf {mountpoint}/EFI/Linux")
    run(f"rm -rf {mountpoint}/EFI/systemd")
    run(f"rm -rf {mountpoint}/EFI/refind")
    run(f"rm -f {mountpoint}/refind_linux.conf")

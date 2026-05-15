# core/helper_disk.py

import os

# ------------------------
# Helpers - Disk
# ------------------------

def get_base_disk(config):
    path = f"/dev/disk/by-id/{config['disk']['disk_by_id']}"
    if not os.path.exists(path):
        raise RuntimeError(f"Base disk not found: {path}")
    return path


def get_partition(base, part_suffix):
    # No suffix — whole-disk device (no partition table)
    if not part_suffix:
        path = f"/dev/disk/by-id/{base}"
        if not os.path.exists(path):
            raise RuntimeError(f"Device not found: {path}")
        return path

    # try namespace (_1)
    path = f"/dev/disk/by-id/{base}_1{part_suffix}"
    if os.path.exists(path):
        return path

    # fallback
    path = f"/dev/disk/by-id/{base}{part_suffix}"
    if not os.path.exists(path):
        raise RuntimeError(f"Device not found: {path} (also tried _1 namespace variant)")
    return path


def get_root_partition(config):
    base = config["disk"]["disk_by_id"]
    part_suffix = config["disk"]["root_part"]
    return get_partition(base, part_suffix)

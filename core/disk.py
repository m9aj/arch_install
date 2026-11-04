# core/disk.py

import os

# ------------------------
# Helpers - Disk
# ------------------------


def get_base_disk(config):
    disk_id = str(config["disk"]["disk_by_id"]).strip()
    path = f"/dev/disk/by-id/{disk_id}"
    if not os.path.exists(path):
        raise RuntimeError(f"Base disk not found: {path}")
    return path


def get_partition(base, part_suffix):
    base = str(base).strip()
    part_suffix = str(part_suffix).strip() if part_suffix else ""

    # No suffix — whole-disk device (no partition table)
    if not part_suffix:
        path = f"/dev/disk/by-id/{base}"
        if not os.path.exists(path):
            raise RuntimeError(f"Device not found: {path}")
        return path

    # Try namespace (_1) for NVMe drives
    path = f"/dev/disk/by-id/{base}_1{part_suffix}"
    if os.path.exists(path):
        return path

    # Fallback to standard suffix
    path = f"/dev/disk/by-id/{base}{part_suffix}"
    if not os.path.exists(path):
        raise RuntimeError(f"Device not found: {path} (also tried _1 namespace variant)")
    return path


def get_root_partition(config):
    base = config["disk"]["disk_by_id"]
    part_suffix = config["disk"]["root_part"]
    return get_partition(base, part_suffix)

# core/validator.py
"""
Fail-fast schema validation for the installer configuration using Python standard library dataclasses.
Runs without internet dependencies or third-party packages.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class DiskConfig:
    disk_by_id: str
    boot_part: str
    root_part: str
    mount_ops_ssd: str = "noatime,compress=zstd:3,ssd,space_cache=v2"
    mount_ops_oth: str = "nosuid,nodev,nofail,x-gvfs-show"
    mount_ops_hdd: str = "noatime,autodefrag"

@dataclass
class RootConfig:
    mode: str = "reuse"
    subvolumes: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class SystemConfig:
    hostname: str
    root_password: str
    username: str
    user_password: str
    timezone: str
    fullname: str = "Ajay Moganti"
    autologin: bool = False

@dataclass
class BootConfig:
    bootloader: str = "systemd-boot"
    init: str = "mkinitcpio"
    kernel_params: List[str] = field(default_factory=list)

@dataclass
class HardwareConfig:
    cpu: str = "auto"
    gpu: str = "auto"

def validate(config: Dict[str, Any]):
    """Validate resolved configuration against mandatory fields and allowed enum values."""
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a dictionary")

    # Disk checks
    require(config, "disk.disk_by_id")
    require(config, "disk.boot_part")
    require(config, "disk.root_part")
    enum(config, "root.mode", ["format", "reuse"])

    # System checks
    require(config, "system.hostname")
    require(config, "system.root_password")
    require(config, "system.username")
    require(config, "system.user_password")
    require(config, "system.timezone")

    # Boot checks
    enum(config, "boot.bootloader", ["systemd-boot", "refind", "none"])
    enum(config, "boot.init", ["mkinitcpio", "dracut", "booster"])

    # Reject explicit disabling of UKI or non-standard boot_mount
    uki_cfg = _get(config, "boot.uki")
    if uki_cfg is False:
        raise ValueError("boot.uki: setting uki to false is no longer supported. UKI is now the default and only boot mode.")

    boot_mount_cfg = _get(config, "boot.boot_mount")
    if boot_mount_cfg and boot_mount_cfg != "/efi":
        raise ValueError(f"boot.boot_mount: {boot_mount_cfg!r} is not supported. The EFI System Partition must be mounted at /efi.")

    # Hardware checks
    enum(config, "hardware.cpu", ["amd", "intel", "auto"])
    enum(config, "hardware.gpu", ["amd", "nvidia", "auto"])

# ------------------------
# Helpers
# ------------------------

def _get(config: Dict[str, Any], path: str) -> Any:
    current = config
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current

def require(config: Dict[str, Any], path: str):
    value = _get(config, path)
    if not value:
        raise ValueError(f"Missing required field: {path}")

def enum(config: Dict[str, Any], path: str, allowed: List[str]):
    value = _get(config, path)
    if not value:
        raise ValueError(f"Missing required field: {path}")
    if value not in allowed:
        raise ValueError(f"Invalid value for {path}: '{value}'. Must be one of: {', '.join(allowed)}")

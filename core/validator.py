# core/validator.py

def validate(config):
    # Disk
    require(config, "disk.disk_by_id")
    require(config, "disk.boot_part")
    require(config, "disk.root_part")
    enum(config, "root.mode", ["format", "reuse"])

    # System
    require(config, "system.hostname")
    require(config, "system.root_password")
    require(config, "system.username")
    require(config, "system.user_password")
    require(config, "system.timezone")

    # Boot
    enum(config, "boot.bootloader", ["systemd-boot", "refind", "none"])
    enum(config, "boot.init",       ["mkinitcpio", "dracut"])

    # Reject explicit disabling of UKI or non-standard boot_mount
    uki_cfg = _get(config, "boot.uki")
    if uki_cfg is False:
        raise ValueError("boot.uki: setting uki to false is no longer supported. UKI is now the default and only boot mode.")

    boot_mount_cfg = _get(config, "boot.boot_mount")
    if boot_mount_cfg and boot_mount_cfg != "/efi":
        raise ValueError(f"boot.boot_mount: {boot_mount_cfg!r} is not supported. The EFI System Partition must be mounted at /efi.")

    # Hardware
    enum(config, "hardware.cpu", ["amd", "intel", "auto"])
    enum(config, "hardware.gpu", ["amd", "nvidia", "auto"])


# ------------------------
# Helpers
# ------------------------

def _get(config, path):
    current = config
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def require(config, path):
    value = _get(config, path)
    if not value:
        raise ValueError(f"Missing required field: {path}")


def enum(config, path, allowed):
    value = _get(config, path)
    if not value:
        raise ValueError(f"Missing required field: {path}")
    if value not in allowed:
        raise ValueError(f"Invalid value for {path}: '{value}'. Must be one of: {', '.join(allowed)}")

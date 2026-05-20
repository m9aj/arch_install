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
    enum(config, "boot.init",       ["mkinitcpio", "dracut", "booster"])

    uki        = bool(_get(config, "boot.uki"))
    bootloader = _get(config, "boot.bootloader")
    init_sys   = _get(config, "boot.init")

    if bootloader == "none" and not uki:
        raise ValueError("boot.bootloader: 'none' requires boot.uki: true — nothing would boot otherwise")
    if uki and init_sys == "booster":
        raise ValueError("boot.uki: true is not supported with init: booster")

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

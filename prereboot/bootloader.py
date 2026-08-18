# preinstall/bootloader.py

import os
import re
import shlex
from core.shell import run, chroot
from core.disk import get_root_partition
from core.resolver import resolve_system, detect_gpu
from core.logger import logger


def install_bootloader(config):
    bootloader = config.get("boot", {}).get("bootloader", "systemd-boot")
    init       = config.get("boot", {}).get("init", "mkinitcpio")

    logger.info(f"Installing bootloader: {bootloader}  (init: {init}, UKI mode)")

    _clean_unused_bootloaders(bootloader)
    _clean_stale_arch_efi_entries()

    generate_initramfs(config)

    if bootloader == "systemd-boot":
        install_systemd_boot(config)
    elif bootloader == "limine":
        install_limine(config)
    elif bootloader == "none":
        register_uki_efi(config)
    else:
        raise ValueError(f"Unsupported bootloader: {bootloader!r}")


def _clean_unused_bootloaders(selected_bootloader):
    boot_mount = "/mnt/efi"
    if selected_bootloader != "limine":
        run(f"rm -rf {boot_mount}/EFI/limine {boot_mount}/limine.conf {boot_mount}/EFI/BOOT/limine.conf", check=False)
    if selected_bootloader != "systemd-boot":
        run(f"rm -rf {boot_mount}/EFI/systemd", check=False)


def _clean_stale_arch_efi_entries():
    logger.info("Cleaning stale Linux/Arch EFI boot entries from UEFI NVRAM...")
    out = run("efibootmgr -v", check=False).stdout
    target_keywords = ["arch", "limine", "refind", "systemd-boot", "\\efi\\limine", "\\efi\\linux", "\\efi\\refind"]
    for line in out.splitlines():
        match = re.match(r"^Boot([0-9A-Fa-f]{4})\*?\s+(.*)$", line)
        if match:
            boot_num = match.group(1)
            entry_info = match.group(2).lower()
            if any(kw in entry_info for kw in target_keywords):
                logger.info(f"Deleting stale EFI boot entry {boot_num}: {line.strip()}")
                run(f"efibootmgr -b {boot_num} -B", check=False)


# ------------------------
# Initramfs / UKI
# ------------------------

def generate_initramfs(config):
    boot   = config.get("boot", {})
    init   = boot.get("init", "mkinitcpio")
    kernel = boot.get("kernel", "linux")
    boot_mount = "/efi"

    _write_kernel_cmdline(config)
    _configure_kernel_install(config)
    _setup_nvidia_kms(config)
    if init == "mkinitcpio":
        _patch_mkinitcpio_preset_for_uki(config)
        chroot("mkinitcpio -P")
    elif init == "dracut":
        efi        = uki_filename(config)
        run(f"mkdir -p /mnt{boot_mount}/EFI/Linux")
        chroot(f"dracut --uefi --force --hostonly --kernel-cmdline \"$(cat /etc/kernel/cmdline)\" {boot_mount}/EFI/Linux/{efi}")

        # Create pacman hook to automatically update UKI when the kernel, microcode, or systemd updates
        hooks_dir = "/mnt/etc/pacman.d/hooks"
        run(f"mkdir -p {hooks_dir}")
        hook_content = f"""[Trigger]
Type = Path
Operation = Install
Operation = Upgrade
Operation = Remove
Target = usr/lib/modules/*/vmlinuz
Target = usr/lib/firmware/*
Target = usr/lib/systemd/boot/efi/*

[Action]
Description = Updating Unified Kernel Images (UKIs) on ESP via dracut...
When = PostTransaction
Exec = /usr/bin/bash -c 'for pkgbase in /usr/lib/modules/*/pkgbase; do [ -f "$pkgbase" ] || continue; kver=$(basename $(dirname $pkgbase)); pkgname=$(cat "$pkgbase"); /usr/bin/dracut --uefi --force --hostonly --kernel-cmdline "$(cat /etc/kernel/cmdline)" {boot_mount}/EFI/Linux/arch-${{pkgname}}.efi --kver "$kver"; done'
"""
        with open(f"{hooks_dir}/90-dracut-uki.hook", "w") as f:
            f.write(hook_content)
    else:
        raise ValueError(f"Unsupported init system for UKI: {init!r}")


def _write_kernel_cmdline(config):
    root_part = get_root_partition(config)
    system    = resolve_system(config)
    params    = list(system.get("kernel_params", []))

    if "rootflags=subvol=@" not in " ".join(params):
        params.append("rootflags=subvol=@")

    uuid_res = run(f"blkid -s UUID -o value {root_part}").stdout.strip()
    uuid = uuid_res.splitlines()[0] if uuid_res else ""
    run("mkdir -p /mnt/etc/kernel")
    run(f"echo 'root=UUID={uuid} {' '.join(params)}' > /mnt/etc/kernel/cmdline")


def _configure_kernel_install(config):
    init = config.get("boot", {}).get("init", "mkinitcpio")
    run("mkdir -p /mnt/etc/kernel")
    run(f"""cat > /mnt/etc/kernel/install.conf <<_EOF_
layout=uki
initrd_generator={init}
_EOF_""")


def _patch_mkinitcpio_preset_for_uki(config):
    boot       = config.get("boot", {})
    kernel     = boot.get("kernel", "linux")
    boot_mount = "/efi"
    main_uki   = uki_filename(config)

    run(f"mkdir -p /mnt{boot_mount}/EFI/Linux /mnt/etc/mkinitcpio.d")
    run(f"""cat > /mnt/etc/mkinitcpio.d/{kernel}.preset <<'_EOF_'
ALL_config="/etc/mkinitcpio.conf"
ALL_kver="/boot/vmlinuz-{kernel}"

PRESETS=('default')

default_uki="{boot_mount}/EFI/Linux/{main_uki}"
default_options="--cmdline /etc/kernel/cmdline"
_EOF_""")


def uki_filename(config):
    kernel = config.get("boot", {}).get("kernel", "linux")
    return f"arch-{kernel}.efi"


# ------------------------
# systemd-boot
# ------------------------

def install_systemd_boot(config):
    boot_mount = "/efi"
    chroot(f"bootctl --esp-path={boot_mount} install")

    configure_systemd_boot(config)
    logger.info("UKI mode: skipping entry file — systemd-boot auto-discovers EFI/Linux/*.efi")


def configure_systemd_boot(config):
    boot         = config.get("boot", {})
    boot_mount   = "/efi"
    sd_cfg       = boot.get("systemd-boot", {})
    timeout      = sd_cfg.get("timeout", 3)
    console_mode = sd_cfg.get("console-mode", "auto")
    editor_val   = sd_cfg.get("editor", "no")
    editor       = "yes" if editor_val is True else "no" if editor_val is False else editor_val

    run(f"mkdir -p /mnt{boot_mount}/loader")
    run(f"""cat > /mnt{boot_mount}/loader/loader.conf <<_EOF_
default arch
timeout {timeout}
console-mode {console_mode}
editor {editor}
_EOF_""")


# ------------------------
# UEFI direct (bootloader: none)
# ------------------------

def register_uki_efi(config):
    disk_by_id = config["disk"]["disk_by_id"]
    boot_part  = config["disk"]["boot_part"]
    label      = config.get("arch", {}).get("label", "Arch")
    de         = config.get("arch", {}).get("de", "")
    title      = f"{label} {de.capitalize()}".strip()
    efi        = uki_filename(config)

    boot_dev_path = run(f"readlink -f /dev/disk/by-id/{disk_by_id}{boot_part}").stdout.strip()
    part_name     = os.path.basename(boot_dev_path)
    disk_name     = run(f"lsblk -no PKNAME {boot_dev_path}").stdout.strip()
    part_num      = run(f"cat /sys/class/block/{part_name}/partition").stdout.strip()

    # Check if an entry with the same partition UUID and loader path already exists
    try:
        partuuid = run(f"blkid -s PARTUUID -o value {boot_dev_path}").stdout.strip().lower()
        if partuuid:
            efiboot_out = run("efibootmgr -v", check=False).stdout.lower()
            normalized_loader = f"\\efi\\linux\\{efi.lower()}".replace("\\\\", "\\")
            
            exists = False
            for line in efiboot_out.splitlines():
                # Normalize line backslashes to handle variation in efibootmgr representation
                normalized_line = line.replace("\\\\", "\\")
                if partuuid in normalized_line and normalized_loader in normalized_line:
                    logger.info(f"EFI boot entry already exists for {efi} on partition {partuuid}. Skipping creation.")
                    exists = True
                    break
            if exists:
                return
    except Exception as e:
        logger.warning(f"Failed to check existing EFI boot entries: {e}. Proceeding with creation.")

    run(f"efibootmgr --create --disk /dev/{disk_name} --part {part_num} "
        f"--label {shlex.quote(title)} --loader '\\EFI\\Linux\\{efi}'")



def _setup_nvidia_kms(config):
    gpu_cfg = config.get("hardware", {}).get("gpu", "auto")
    gpu = detect_gpu() if gpu_cfg == "auto" else gpu_cfg
    if gpu != "nvidia":
        return

    init = config.get("boot", {}).get("init", "mkinitcpio")
    logger.info("Setting up Nvidia Early KMS...")
    if init == "mkinitcpio":
        _enable_nvidia_kms_mkinitcpio()
    elif init == "dracut":
        _enable_nvidia_kms_dracut()


def _enable_nvidia_kms_mkinitcpio():
    path = "/mnt/etc/mkinitcpio.conf"
    if not os.path.exists(path):
        logger.warning(f"{path} not found. Skipping Nvidia early KMS setup.")
        return

    with open(path, "r") as f:
        content = f.read()

    import re
    # Match MODULES=(...) and capture the contents inside parentheses.
    # Note: re.DOTALL in case it is multi-line.
    match = re.search(r'^MODULES=\((.*?)\)', content, re.MULTILINE | re.DOTALL)
    if match:
        existing = match.group(1).strip()
        existing_mods = existing.split()
        nvidia_mods = ["nvidia", "nvidia_modeset", "nvidia_uvm", "nvidia_drm"]
        missing = [m for m in nvidia_mods if m not in existing_mods]
        if missing:
            new_mods = " ".join(existing_mods + missing)
            span = match.span(1)
            content = content[:span[0]] + new_mods + content[span[1]:]
            with open(path, "w") as f:
                f.write(content)
            logger.info(f"Added Nvidia modules to MODULES in {path}")
    else:
        logger.warning(f"Could not parse MODULES array in {path}")


def _enable_nvidia_kms_dracut():
    dir_path = "/mnt/etc/dracut.conf.d"
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, "nvidia.conf")
    
    content = 'force_drivers+=" nvidia nvidia_modeset nvidia_uvm nvidia_drm "\n'
    with open(file_path, "w") as f:
        f.write(content)
    logger.info(f"Created {file_path} for Nvidia early KMS")


# ------------------------
# Limine
# ------------------------

def install_limine(config):
    boot_mount = "/efi"
    kernel = config.get("boot", {}).get("kernel", "linux")
    uki_name = uki_filename(config)
    limine_cfg = config.get("boot", {}).get("limine", {})

    logger.info("Installing Limine bootloader...")
    run(f"mkdir -p /mnt{boot_mount}/EFI/limine /mnt{boot_mount}/EFI/BOOT")
    chroot("cp /usr/share/limine/BOOTX64.EFI /efi/EFI/limine/limine.efi")
    chroot("cp /usr/share/limine/BOOTX64.EFI /efi/EFI/BOOT/BOOTX64.EFI")

    timeout = limine_cfg.get("timeout", 3)

    remember_val = limine_cfg.get("remember_last_entry", True)
    remember = "yes" if remember_val is True else "no" if remember_val is False else str(remember_val)

    verbose_val = limine_cfg.get("verbose", False)
    verbose = "yes" if verbose_val is True else "no" if verbose_val is False else str(verbose_val)

    branding = limine_cfg.get("interface_branding", "auto")
    if branding == "auto" or not branding:
        branding = config.get("system", {}).get("hostname") or "Arch Linux"

    branding_colour = limine_cfg.get("interface_branding_colour", "CCCCCC")

    help_hidden_val = limine_cfg.get("interface_help_hidden", True)
    help_hidden = "yes" if help_hidden_val is True else "no" if help_hidden_val is False else str(help_hidden_val)

    help_colour = limine_cfg.get("interface_help_colour", "CCCCCC")
    term_bg = limine_cfg.get("term_background", "DD000000")
    term_fg = limine_cfg.get("term_foreground", "FFFFFF")
    font_scale = limine_cfg.get("term_font_scale", "2x2")
    term_margin = limine_cfg.get("term_margin", 0)

    # Wallpaper configuration
    wallpaper_cfg = limine_cfg.get("wallpaper", True)
    wallpaper_style = limine_cfg.get("wallpaper_style", "stretched")
    wallpaper_setting = ""

    if wallpaper_cfg:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if isinstance(wallpaper_cfg, str) and wallpaper_cfg.lower() not in ("true", "yes"):
            wallpaper_src = wallpaper_cfg if os.path.isabs(wallpaper_cfg) else os.path.join(repo_root, wallpaper_cfg)
        else:
            wallpaper_src = os.path.join(repo_root, "assets", "limine-wallpaper.jpg")

        if os.path.exists(wallpaper_src):
            logger.info(f"Copying Limine background image from assets ({wallpaper_src}) to ESP...")
            run(f"cp {shlex.quote(wallpaper_src)} /mnt{boot_mount}/EFI/limine/wallpaper.jpg", check=False)
            wallpaper_setting = (
                "wallpaper: boot():/EFI/limine/wallpaper.jpg\n"
                f"wallpaper_style: {wallpaper_style}\n"
            )

    limine_conf = f"""timeout: {timeout}
verbose: {verbose}
remember_last_entry: {remember}

interface_branding: {branding}
interface_branding_colour: {branding_colour}
interface_help_hidden: {help_hidden}
interface_help_colour: {help_colour}

{wallpaper_setting}term_background: {term_bg}
term_foreground: {term_fg}

term_font_scale: {font_scale}
term_margin: {term_margin}

/Arch Linux
    protocol: efi_chainload
    image_path: boot():/EFI/Linux/{uki_name}
"""
    if os.path.exists(f"/mnt{boot_mount}/EFI/Microsoft/Boot/bootmgfw.efi"):
        logger.info("Windows Boot Manager detected on ESP, adding Windows entry to Limine config...")
        limine_conf += """
/Windows 11 Pro
    protocol: efi_chainload
    image_path: boot():/EFI/Microsoft/Boot/bootmgfw.efi
"""
    for conf_path in [
        f"/mnt{boot_mount}/limine.conf",
        f"/mnt{boot_mount}/EFI/limine/limine.conf",
        f"/mnt{boot_mount}/EFI/BOOT/limine.conf",
    ]:
        with open(conf_path, "w") as f:
            f.write(limine_conf)

    register_limine_efi(config)


def register_limine_efi(config):
    disk_by_id = config["disk"]["disk_by_id"]
    boot_part  = config["disk"]["boot_part"]
    label      = config.get("arch", {}).get("label", "Arch")
    de         = config.get("arch", {}).get("de", "")
    title      = f"{label} Limine".strip()

    boot_dev_path = run(f"readlink -f /dev/disk/by-id/{disk_by_id}{boot_part}").stdout.strip()
    part_name     = os.path.basename(boot_dev_path)
    disk_name     = run(f"lsblk -no PKNAME {boot_dev_path}").stdout.strip()
    part_num      = run(f"cat /sys/class/block/{part_name}/partition").stdout.strip()

    run(f"efibootmgr --create --disk /dev/{disk_name} --part {part_num} "
        f"--label {shlex.quote(title)} --loader '\\EFI\\limine\\limine.efi'", check=False)

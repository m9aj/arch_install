# preinstall/bootloader.py

import os
import shlex
from core.helper_basic import run, chroot
from core.helper_disk import get_root_partition
from core.resolver import resolve_system
from core.logger import logger


def install_bootloader(config):
    bootloader = config.get("boot", {}).get("bootloader", "systemd-boot")
    init       = config.get("boot", {}).get("init", "mkinitcpio")
    uki        = config.get("boot", {}).get("uki", False)

    logger.info(f"Installing bootloader: {bootloader}  (init: {init}, uki: {uki})")

    generate_initramfs(config)

    if bootloader == "systemd-boot":
        install_systemd_boot(config)
    elif bootloader == "refind":
        install_refind(config)
    elif bootloader == "none":
        register_uki_efi(config)
    else:
        raise ValueError(f"Unsupported bootloader: {bootloader!r}")


# ------------------------
# Initramfs / UKI
# ------------------------

def generate_initramfs(config):
    boot   = config.get("boot", {})
    init   = boot.get("init", "mkinitcpio")
    kernel = boot.get("kernel", "linux")
    uki    = boot.get("uki", False)

    if uki:
        _write_kernel_cmdline(config)
        if init == "mkinitcpio":
            _patch_mkinitcpio_preset_for_uki(config)
            chroot("mkinitcpio -P")
        elif init == "dracut":
            efi        = uki_filename(config)
            boot_mount = boot.get("boot_mount", "/boot")
            run(f"mkdir -p /mnt{boot_mount}/EFI/Linux")
            chroot(f"dracut --uefi --force --hostonly {boot_mount}/EFI/Linux/{efi}")
        return

    if init == "mkinitcpio":
        chroot("mkinitcpio -P")
    elif init == "dracut":
        chroot(f"dracut --force --hostonly /boot/initramfs-{kernel}.img")
    elif init == "booster":
        chroot(f"booster build --force /boot/booster-{kernel}.img")
    else:
        raise ValueError(f"Unsupported init system: {init!r}")


def _write_kernel_cmdline(config):
    root_part = get_root_partition(config)
    system    = resolve_system(config)
    params    = list(system.get("kernel_params", []))

    if "rootflags=subvol=@" not in " ".join(params):
        params.append("rootflags=subvol=@")

    uuid = run(f"blkid -s UUID -o value {root_part}").stdout.strip()
    run("mkdir -p /mnt/etc/kernel")
    run(f"echo 'root=UUID={uuid} {' '.join(params)}' > /mnt/etc/kernel/cmdline")


def _patch_mkinitcpio_preset_for_uki(config):
    boot       = config.get("boot", {})
    kernel     = boot.get("kernel", "linux")
    boot_mount = boot.get("boot_mount", "/boot")
    main_uki   = uki_filename(config)

    run(f"mkdir -p /mnt{boot_mount}/EFI/Linux /mnt/etc/mkinitcpio.d")
    run(f"""cat > /mnt/etc/mkinitcpio.d/{kernel}.preset <<'_EOF_'
ALL_config="/etc/mkinitcpio.conf"
ALL_kver="/boot/vmlinuz-{kernel}"
ALL_microcode=(/boot/*-ucode.img)

PRESETS=('default')

default_uki="{boot_mount}/EFI/Linux/{main_uki}"
default_options=""
_EOF_""")


def uki_filename(config):
    kernel = config.get("boot", {}).get("kernel", "linux")
    return f"arch-{kernel}.efi"


def initramfs_filename(config):
    boot   = config.get("boot", {})
    init   = boot.get("init", "mkinitcpio")
    kernel = boot.get("kernel", "linux")
    if init == "booster":
        return f"booster-{kernel}.img"
    return f"initramfs-{kernel}.img"


# ------------------------
# systemd-boot
# ------------------------

def install_systemd_boot(config):
    boot       = config.get("boot", {})
    uki        = boot.get("uki", False)
    boot_mount = boot.get("boot_mount", "/boot")
    chroot(f"bootctl --esp-path={boot_mount} install")


    configure_systemd_boot(config)

    if uki:
        logger.info("UKI mode: skipping entry file — systemd-boot auto-discovers EFI/Linux/*.efi")
    else:
        generate_systemd_boot_entry(config)


def configure_systemd_boot(config):
    boot         = config.get("boot", {})
    boot_mount   = boot.get("boot_mount", "/boot")
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


def generate_systemd_boot_entry(config):
    root_part  = get_root_partition(config)
    boot       = config.get("boot", {})
    kernel     = boot.get("kernel", "linux")
    boot_mount = boot.get("boot_mount", "/boot")
    label      = config.get("arch", {}).get("label", "Arch")
    de         = config.get("arch", {}).get("de", "")
    title      = f"{label} {de.capitalize()}".strip()
    initrd_img = initramfs_filename(config)

    system = resolve_system(config)
    params = list(system.get("kernel_params", []))
    if "rootflags=subvol=@" not in " ".join(params):
        params.append("rootflags=subvol=@")
    param_str = " ".join(params)

    cpu = config.get("hardware", {}).get("cpu", "auto")
    if cpu == "auto":
        from core.resolver import detect_cpu
        cpu = detect_cpu()

    ucode_line = ""
    if cpu == "intel":
        ucode_line = "initrd  /intel-ucode.img"
    elif cpu == "amd":
        ucode_line = "initrd  /amd-ucode.img"

    uuid = run(f"blkid -s UUID -o value {root_part}").stdout.strip()
    run(f"mkdir -p /mnt{boot_mount}/loader/entries")
    run(f"""cat > /mnt{boot_mount}/loader/entries/arch.conf <<_EOF_
title   {title}
linux   /vmlinuz-{kernel}
{ucode_line}
initrd  /{initrd_img}
options root=UUID={uuid} {param_str}
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



# ------------------------
# rEFInd
# ------------------------

def install_refind(config):
    boot = config.get("boot", {})
    uki = boot.get("uki", False)
    boot_mount = boot.get("boot_mount", "/boot")

    # Run refind-install in the chroot environment.
    logger.info("Installing rEFInd via refind-install inside chroot")
    chroot("refind-install")

    if uki:
        logger.info("rEFInd: UKI mode enabled. Kernels will be auto-scanned from EFI/Linux.")
    else:
        generate_refind_linux_conf(config)

    # Further configuration of rEFInd
    refind_conf_path = f"/mnt{boot_mount}/EFI/refind/refind.conf"
    if os.path.exists(refind_conf_path):
        logger.info(f"Configuring rEFInd resolution in {refind_conf_path}")
        with open(refind_conf_path, "r") as f:
            content = f.read()

        # Set resolution to max
        import re
        if re.search(r"^\s*resolution\s+", content, re.MULTILINE):
            content = re.sub(r"^\s*resolution\s+.*$", "resolution max", content, flags=re.MULTILINE)
        elif re.search(r"^\s*#\s*resolution\s+", content, re.MULTILINE):
            content = re.sub(r"^\s*#\s*resolution\s+.*$", "resolution max", content, flags=re.MULTILINE)
        else:
            content += "\nresolution max\n"

        # Install digital-void theme
        theme_dir = f"/mnt{boot_mount}/EFI/refind/themes"
        theme_path = f"{theme_dir}/rEFInd-digital-void"
        logger.info("Installing rEFInd theme: rEFInd-digital-void")
        run(f"mkdir -p {theme_dir}")
        theme_installed = False
        if not os.path.exists(theme_path):
            try:
                run(f"git clone https://github.com/Wi-Fight-IT/rEFInd-digital-void {theme_path}")
                theme_installed = True
            except Exception as e:
                logger.warning(f"Failed to clone rEFInd theme: {e}. Skipping theme configuration.")
        else:
            logger.info("Theme already cloned, skipping clone")
            theme_installed = True

        # Append theme include if not already present
        if theme_installed and "include themes/rEFInd-digital-void/theme.conf" not in content:
            content += "\ninclude themes/rEFInd-digital-void/theme.conf\n"

        with open(refind_conf_path, "w") as f:
            f.write(content)

    # Set Arch Linux logo for boot entries (copy os_arch.png)
    src_icon = "/mnt/usr/share/refind/icons/os_arch.png"
    if os.path.exists(src_icon):
        import glob
        # For standard kernels in /boot (represented as /mnt/boot/)
        for kernel in glob.glob("/mnt/boot/vmlinuz-*"):
            logger.info(f"Copying Arch icon for standard kernel {kernel} to {kernel}.png")
            run(f"cp {src_icon} {kernel}.png")
        # For UKIs in EFI/Linux
        for uki_file in glob.glob(f"/mnt{boot_mount}/EFI/Linux/*.efi"):
            # Set icon for both .png and .efi.png filenames for robustness
            base_name, _ = os.path.splitext(uki_file)
            logger.info(f"Copying Arch icon for UKI entry to {base_name}.png")
            run(f"cp {src_icon} {base_name}.png")
            run(f"cp {src_icon} {uki_file}.png")
    else:
        logger.warning(f"Could not find Arch icon at {src_icon} to copy for boot entries")

    # Set up automatic updates for rEFInd via a pacman hook
    hooks_dir = "/mnt/etc/pacman.d/hooks"
    hook_path = f"{hooks_dir}/refind.hook"
    logger.info(f"Creating pacman hook for automatic rEFInd updates at {hook_path}")
    run(f"mkdir -p {hooks_dir}")
    hook_content = """[Trigger]
Operation = Upgrade
Type = Package
Target = refind

[Action]
Description = Updating rEFInd on ESP...
When = PostTransaction
Exec = /usr/bin/refind-install
"""
    with open(hook_path, "w") as f:
        f.write(hook_content)


def generate_refind_linux_conf(config):
    root_part  = get_root_partition(config)
    boot       = config.get("boot", {})
    boot_mount = boot.get("boot_mount", "/boot")
    
    system = resolve_system(config)
    params = list(system.get("kernel_params", []))
    if "rootflags=subvol=@" not in " ".join(params):
        params.append("rootflags=subvol=@")
    param_str = " ".join(params)

    uuid = run(f"blkid -s UUID -o value {root_part}").stdout.strip()
    
    cpu = config.get("hardware", {}).get("cpu", "auto")
    if cpu == "auto":
        from core.resolver import detect_cpu
        cpu = detect_cpu()

    ucode_img = None
    if cpu == "intel":
        ucode_img = "intel-ucode.img"
    elif cpu == "amd":
        ucode_img = "amd-ucode.img"

    if ucode_img:
        initrd_img = initramfs_filename(config)
        opts = f"initrd=/{ucode_img} initrd=/{initrd_img} root=UUID={uuid} rw {param_str}"
        single_opts = f"initrd=/{ucode_img} initrd=/{initrd_img} root=UUID={uuid} rw {param_str} single"
        minimal_opts = f"initrd=/{ucode_img} initrd=/{initrd_img} root=UUID={uuid} rw"
    else:
        opts = f"root=UUID={uuid} rw {param_str}"
        single_opts = f"root=UUID={uuid} rw {param_str} single"
        minimal_opts = f"root=UUID={uuid} rw"

    conf_path = f"/mnt{boot_mount}/refind_linux.conf"
    logger.info(f"Writing rEFInd kernel configuration to {conf_path}")
    
    run(f"""cat > {conf_path} <<_EOF_
"Boot with standard options"  "{opts}"
"Boot to single-user mode"    "{single_opts}"
"Boot with minimal options"   "{minimal_opts}"
_EOF_""")



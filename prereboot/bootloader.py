# preinstall/bootloader.py

import os
import shlex
from core.shell import run, chroot
from core.disk import get_root_partition
from core.resolver import resolve_system, detect_gpu
from core.logger import logger


def install_bootloader(config):
    bootloader = config.get("boot", {}).get("bootloader", "systemd-boot")
    init       = config.get("boot", {}).get("init", "mkinitcpio")

    logger.info(f"Installing bootloader: {bootloader}  (init: {init}, UKI mode)")

    generate_initramfs(config)

    if bootloader == "systemd-boot":
        install_systemd_boot(config)
    elif bootloader == "refind":
        install_refind(config)
    elif bootloader == "limine":
        install_limine(config)
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



# ------------------------
# rEFInd
# ------------------------

def install_refind(config):
    boot_mount = "/efi"

    # Run refind-install in the chroot environment.
    logger.info("Installing rEFInd via refind-install inside chroot")
    chroot("refind-install")

    logger.info("rEFInd: UKI mode enabled. Kernels will be auto-scanned from EFI/Linux.")

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
                import shutil
                if not shutil.which("git"):
                    logger.info("git is not installed on the live ISO. Attempting to install it...")
                    run("pacman -Sy --noconfirm git")
                run(f"git clone https://github.com/Wi-Fight-IT/rEFInd-digital-void {theme_path}")
                theme_installed = True
            except Exception as e:
                logger.warning(f"Failed to install git or clone rEFInd theme: {e}. Skipping theme configuration.")
        else:
            logger.info("Theme already cloned, skipping clone")
            theme_installed = True

        # Append theme include if not already present
        if theme_installed and "include themes/rEFInd-digital-void/theme.conf" not in content:
            content += "\ninclude themes/rEFInd-digital-void/theme.conf\n"

        # Exclude raw kernel from scanning to prevent duplicate UKI entries
        if "dont_scan_files +,vmlinuz-linux" not in content:
            if "#dont_scan_files shim.efi,MokManager.efi" in content:
                content = content.replace(
                    "#dont_scan_files shim.efi,MokManager.efi",
                    "#dont_scan_files shim.efi,MokManager.efi\ndont_scan_files +,vmlinuz-linux"
                )
            else:
                content += "\ndont_scan_files +,vmlinuz-linux\n"

        with open(refind_conf_path, "w") as f:
            f.write(content)

        # Update the theme config file to set background to background.blue.png
        if theme_installed:
            theme_conf_path = f"{theme_path}/theme.conf"
            if os.path.exists(theme_conf_path):
                logger.info(f"Setting blue background in {theme_conf_path}")
                with open(theme_conf_path, "r") as f:
                    theme_conf_content = f.read()

                # Replace banner line
                import re
                if re.search(r"^\s*banner\s+", theme_conf_content, re.MULTILINE):
                    theme_conf_content = re.sub(
                        r"^\s*banner\s+.*$",
                        "banner themes/rEFInd-digital-void/background.blue.png",
                        theme_conf_content,
                        flags=re.MULTILINE
                    )
                else:
                    theme_conf_content += "\nbanner themes/rEFInd-digital-void/background.blue.png\n"

                with open(theme_conf_path, "w") as f:
                    f.write(theme_conf_content)

    # Set Arch Linux logo for boot entries (copy os_arch.png)
    src_icon = None
    theme_icon = f"/mnt{boot_mount}/EFI/refind/themes/rEFInd-digital-void/icons/os_arch.png"
    fallback_icon = "/mnt/usr/share/refind/icons/os_arch.png"

    if os.path.exists(theme_icon):
        src_icon = theme_icon
        logger.info(f"Using theme Arch icon: {src_icon}")
    elif os.path.exists(fallback_icon):
        src_icon = fallback_icon
        logger.info(f"Using fallback system Arch icon: {src_icon}")

    if src_icon:
        import glob
        # For UKIs in EFI/Linux
        for uki_file in glob.glob(f"/mnt{boot_mount}/EFI/Linux/*.efi"):
            # Set icon for both .png and .efi.png filenames for robustness
            base_name, _ = os.path.splitext(uki_file)
            logger.info(f"Copying Arch icon for UKI entry to {base_name}.png")
            run(f"cp {src_icon} {base_name}.png")
            run(f"cp {src_icon} {uki_file}.png")
    else:
        logger.warning("Could not find any Arch icon to copy for boot entries")

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

    logger.info("Installing Limine bootloader...")
    run(f"mkdir -p /mnt{boot_mount}/EFI/limine /mnt{boot_mount}/EFI/BOOT")
    chroot("cp /usr/share/limine/BOOTX64.EFI /efi/EFI/limine/limine.efi")
    chroot("cp /usr/share/limine/BOOTX64.EFI /efi/EFI/BOOT/BOOTX64.EFI")

    limine_conf = f"""timeout: 3
verbose: no

/:Arch Linux ({kernel})
    protocol: efi_uki
    image_path: boot():/EFI/Linux/{uki_name}
"""
    with open(f"/mnt{boot_mount}/limine.conf", "w") as f:
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

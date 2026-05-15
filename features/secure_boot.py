# features/secure_boot.py
# Enrolls Secure Boot keys and signs the kernel and bootloader with sbctl.
# Phase: postboot (after first reboot).

import sys
import os
import shlex
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_basic import run
from core.logger import logger

PACMAN_PACKAGES = ["sbctl"]
AUR_PACKAGES = []
SERVICES = []


def configure(config, feature):
    boot       = config.get("boot", {})
    bootloader = boot.get("bootloader", "systemd-boot")
    uki        = boot.get("uki", False)
    kernel     = boot.get("kernel", "linux")

    run("sudo sbctl create-keys")
    run("sudo sbctl enroll-keys --microsoft")

    if uki:
        # The UKI embeds kernel + initramfs — sign the .efi bundles only.
        run(f"sudo sbctl sign -s /boot/EFI/Linux/arch-{kernel}.efi || true")
        run(f"sudo sbctl sign -s /boot/EFI/Linux/arch-{kernel}-fallback.efi || true")
        # Sign bootloader binary if one is present alongside the UKI.
        if bootloader == "systemd-boot":
            run("sudo sbctl sign -s /boot/EFI/systemd/systemd-bootx64.efi || true")
            run("sudo sbctl sign -s /boot/EFI/BOOT/BOOTX64.EFI || true")
        # bootloader: none — no bootloader binary to sign
        hook_targets = "Target = linux\nTarget = mkinitcpio"
    else:
        run(f"sudo sbctl sign -s /boot/vmlinuz-{kernel}")
        run("sudo sbctl sign -s /boot/EFI/systemd/systemd-bootx64.efi || true")
        run("sudo sbctl sign -s /boot/EFI/BOOT/BOOTX64.EFI || true")
        hook_targets = "Target = linux\nTarget = systemd-boot"

    run("sudo sbctl verify")

    run("sudo mkdir -p /etc/pacman.d/hooks")
    hook_content = f"""[Trigger]
Operation = Install
Operation = Upgrade
Type = Package
{hook_targets}

[Action]
Description = Signing kernel and bootloader for Secure Boot
When = PostTransaction
Exec = /usr/bin/sbctl sign-all
"""
    run(f"echo {shlex.quote(hook_content)} | sudo tee /etc/pacman.d/hooks/90-secureboot.hook > /dev/null")

    if SERVICES:
        logger.info(f"[secure_boot] Enabling services: {', '.join(SERVICES)}")
        for svc in SERVICES:
            run(f"sudo systemctl enable --now {svc}")

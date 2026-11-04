# core/kernel.py
# Kernel, UKI, and cmdline configuration.
# Provides unified kernel parameter management and UKI regeneration
# across both Phase 1 (live ISO / chroot) and Phase 2 (post-reboot).

import os
import shlex
from core.shell import run, chroot
from core.logger import logger


def _is_prereboot():
    """Detect if running from the Arch Live ISO targeting /mnt."""
    return os.getuid() == 0 and os.path.exists("/mnt/etc")


def get_cmdline_path():
    """Return the absolute path to /etc/kernel/cmdline based on current execution phase."""
    return "/mnt/etc/kernel/cmdline" if _is_prereboot() else "/etc/kernel/cmdline"


def get_kernel_cmdline():
    """Read and return the current contents of the kernel cmdline file as a string."""
    path = get_cmdline_path()
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except PermissionError:
        res = run(f"sudo cat {shlex.quote(path)}", check=False)
        return res.stdout.strip() if res.returncode == 0 else ""


def apply_kernel_parameter(config, param, rebuild=True):
    """
    Ensure the given kernel parameter(s) are present in /etc/kernel/cmdline.
    Handles:
      - Flag parameters (e.g. 'quiet', 'splash')
      - Key-value parameters (e.g. 'zswap.enabled=0' replacing existing 'zswap.enabled=1')
      - Multi-token strings (e.g. 'quiet splash')
    Returns True if parameters were added/modified, False if already up to date.
    Triggers UKI rebuild only when changes occurred and rebuild=True.
    """
    cmdline_path = get_cmdline_path()
    current_content = get_kernel_cmdline()
    current_tokens = current_content.split() if current_content else []

    token_map = {}
    tokens_ordered = []

    for t in current_tokens:
        if "=" in t:
            k = t.split("=", 1)[0]
            token_map[k] = t
        else:
            token_map[t] = t
        tokens_ordered.append(t)

    incoming_params = param.split() if isinstance(param, str) else list(param)
    changed = False

    for item in incoming_params:
        item = item.strip()
        if not item:
            continue

        if "=" in item:
            key = item.split("=", 1)[0]
            if key in token_map:
                if token_map[key] != item:
                    idx = tokens_ordered.index(token_map[key])
                    tokens_ordered[idx] = item
                    token_map[key] = item
                    changed = True
            else:
                tokens_ordered.append(item)
                token_map[key] = item
                changed = True
        else:
            if item not in token_map:
                tokens_ordered.append(item)
                token_map[item] = item
                changed = True

    if not changed:
        return False

    new_content = " ".join(tokens_ordered).strip()
    logger.info(f"[kernel] Updating {cmdline_path}: '{new_content}'")

    cmdline_dir = os.path.dirname(cmdline_path)
    run(f"sudo mkdir -p {shlex.quote(cmdline_dir)}")
    run(f"echo {shlex.quote(new_content)} | sudo tee {shlex.quote(cmdline_path)} > /dev/null")

    if rebuild:
        rebuild_uki(config)

    return True


def rebuild_uki(config):
    """
    Regenerate Unified Kernel Image (UKI) using the configured init tool (mkinitcpio or dracut).
    Dispatches to chroot during Phase 1, or host sudo execution during Phase 2.
    """
    boot = config.get("boot", {})
    init = boot.get("init", "mkinitcpio")
    kernel = boot.get("kernel", "linux")
    boot_mount = boot.get("boot_mount", "/efi")
    efi_name = f"arch-{kernel}.efi"

    logger.info(f"[kernel] Regenerating UKI (init: {init}, kernel: {kernel})")

    if init == "mkinitcpio":
        if _is_prereboot():
            chroot("mkinitcpio -P")
        else:
            run("sudo mkinitcpio -P")

    elif init == "dracut":
        cmdline_file = get_cmdline_path()
        target_dir = f"{'/mnt' if _is_prereboot() else ''}{boot_mount}/EFI/Linux"
        target_efi = f"{target_dir}/{efi_name}"

        run(f"sudo mkdir -p {shlex.quote(target_dir)}")

        if _is_prereboot():
            chroot(
                f'dracut --uefi --force --hostonly --kernel-cmdline "$(cat /etc/kernel/cmdline)" {boot_mount}/EFI/Linux/{efi_name}'
            )
        else:
            run(f'sudo dracut --uefi --force --hostonly --kernel-cmdline "$(cat {cmdline_file})" {target_efi}')

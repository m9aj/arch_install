# core/helper_basic.py

import os
import subprocess
import threading
import shlex
from core.logger import logger

_stderr_log_path = None

def set_stderr_log(path):
    global _stderr_log_path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _stderr_log_path = path


# ------------------------
# Helpers - Basic
# ------------------------

def confirm(msg):
    print(f"[WARNING] {msg}")
    ans = input("Type 'YES' to proceed: ")
    if ans != "YES":
        raise RuntimeError("Aborted")

def run(cmd, check=True, env=None, log_cmd=True):
    if log_cmd:
        logger.info(f"[CMD] {cmd}")
    else:
        logger.info("[CMD] <sensitive command redacted>")

    actual_env = None
    if env:
        actual_env = os.environ.copy()
        actual_env.update({k: str(v) for k, v in env.items()})

    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
        env=actual_env,
    )

    full_stdout = []
    full_stderr = []

    def _drain_stdout():
        for line in iter(process.stdout.readline, ""):
            s = line.strip()
            if s:
                logger.info(s)
                full_stdout.append(s)
        process.stdout.close()

    def _drain_stderr():
        for line in iter(process.stderr.readline, ""):
            s = line.strip()
            if s:
                full_stderr.append(s)
        process.stderr.close()

    t_out = threading.Thread(target=_drain_stdout, daemon=True)
    t_err = threading.Thread(target=_drain_stderr, daemon=True)
    t_out.start()
    t_err.start()
    t_out.join()
    t_err.join()
    return_code = process.wait()

    if full_stderr:
        if _stderr_log_path:
            with open(_stderr_log_path, "a") as f:
                f.write(f"\n[CMD] {cmd}\n")
                f.write("\n".join(full_stderr) + "\n")
        else:
            for line in full_stderr:
                logger.warning(f"[STDERR] {line}")

    if check and return_code != 0:
        logger.error(f"[FAIL] {cmd} (exit code: {return_code})")
        raise Exception(cmd)

    class Result:
        def __init__(self, stdout, returncode):
            self.stdout = stdout
            self.returncode = returncode

    return Result("\n".join(full_stdout), return_code)


def chroot(cmd):
    run(f"""arch-chroot /mnt /bin/bash <<'__CHROOT_EOF__'
{cmd}
__CHROOT_EOF__
""")


def apply_kernel_parameter(config, param):
    """
    Applies a kernel parameter persistently.
    If systemd-boot (non-UKI) is used, updates /boot/loader/entries/arch.conf.
    If UKI is used, updates /etc/kernel/cmdline and regenerates the UKI.
    """
    boot = config.get("boot", {})
    boot_mount = boot.get("boot_mount", "/boot")
    uki = boot.get("uki", False)
    init = boot.get("init", "mkinitcpio")
    kernel = boot.get("kernel", "linux")

    if uki:
        # UKI Mode: Update /etc/kernel/cmdline and regenerate UKI
        cmdline_path = "/etc/kernel/cmdline"
        
        # 1. Update /etc/kernel/cmdline
        if os.path.exists(cmdline_path):
            with open(cmdline_path, "r") as f:
                content = f.read().strip()
        else:
            content = ""

        if param not in content.split():
            logger.info(f"Adding '{param}' to {cmdline_path}")
            new_content = f"{content} {param}".strip()
            # Write to /etc/kernel/cmdline using sudo tee to keep it safe and support root-only paths
            run(f"echo {shlex.quote(new_content)} | sudo tee {cmdline_path} > /dev/null")
            
            # 2. Regenerate UKI
            logger.info("Regenerating UKI after kernel parameter update")
            if init == "mkinitcpio":
                run("sudo mkinitcpio -P")
            elif init == "dracut":
                efi_name = f"arch-{kernel}.efi"
                run(f"sudo mkdir -p {boot_mount}/EFI/Linux")
                run(f"sudo dracut --uefi --force --hostonly {boot_mount}/EFI/Linux/{efi_name}")
    else:
        # Non-UKI / systemd-boot Mode
        boot_entry = f"{boot_mount}/loader/entries/arch.conf"
        if os.path.exists(boot_entry):
            logger.info(f"Updating {boot_entry} with kernel parameter: {param}")
            check_cmd = f"grep -q '{param}' {boot_entry}"
            if run(f"{check_cmd}", check=False).returncode != 0:
                run(f"sudo sed -i '/^options/ s/$/ {param}/' {boot_entry}")
        else:
            logger.warning(f"Could not find {boot_entry} to apply kernel parameter '{param}'")


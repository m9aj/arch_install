# core/shell.py

import os
import subprocess
import threading
import shlex
from core.logger import logger, get_stderr_log_path


# -----------------------------------------------------------------------------
# Exception & Result Data Structures
# -----------------------------------------------------------------------------
class CommandError(RuntimeError):
    def __init__(self, cmd, returncode, stdout="", stderr=""):
        super().__init__(f"[FAIL] {cmd} (exit code: {returncode})")
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class Result:
    def __init__(self, stdout, stderr, returncode):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


# -----------------------------------------------------------------------------
# User Interaction Helpers
# -----------------------------------------------------------------------------
def confirm(msg):
    print(f"[WARNING] {msg}")
    ans = input("Type 'YES' to proceed: ")
    if ans != "YES":
        raise RuntimeError("Aborted")


# -----------------------------------------------------------------------------
# Main Subprocess Runner
# -----------------------------------------------------------------------------
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

    stdout_str = "\n".join(full_stdout)
    stderr_str = "\n".join(full_stderr)

    if full_stderr:
        stderr_log = get_stderr_log_path()
        if stderr_log:
            with open(stderr_log, "a") as f:
                f.write(f"\n[CMD] {cmd}\n")
                f.write(stderr_str + "\n")
        else:
            for line in full_stderr:
                logger.warning(f"[STDERR] {line}")

    if check and return_code != 0:
        logger.error(f"[FAIL] {cmd} (exit code: {return_code})")
        raise CommandError(cmd, return_code, stdout_str, stderr_str)

    return Result(stdout_str, stderr_str, return_code)


# -----------------------------------------------------------------------------
# Arch Chroot Wrapper
# -----------------------------------------------------------------------------

def chroot(cmd):
    run(f"""arch-chroot /mnt /bin/bash <<'__CHROOT_EOF__'
{cmd}
__CHROOT_EOF__
""")


# -----------------------------------------------------------------------------
# Kernel Parameter Management
# -----------------------------------------------------------------------------

def apply_kernel_parameter(config, param):
    boot = config.get("boot", {})
    init = boot.get("init", "mkinitcpio")
    kernel = boot.get("kernel", "linux")
    boot_mount = "/efi"

    cmdline_path = "/mnt/etc/kernel/cmdline" if os.path.exists("/mnt/etc/kernel") and os.getuid() == 0 else "/etc/kernel/cmdline"
    
    if os.path.exists(cmdline_path):
        with open(cmdline_path, "r") as f:
            content = f.read().strip()
    else:
        content = ""

    if param not in content.split():
        logger.info(f"Adding '{param}' to {cmdline_path}")
        new_content = f"{content} {param}".strip()

        run(f"echo {shlex.quote(new_content)} | sudo tee {cmdline_path} > /dev/null")
        
        logger.info("Regenerating UKI after kernel parameter update")
        if init == "mkinitcpio":
            run("sudo mkinitcpio -P")
        elif init == "dracut":
            efi_name = f"arch-{kernel}.efi"
            run(f"sudo mkdir -p {boot_mount}/EFI/Linux")
            run(f"sudo dracut --uefi --force --hostonly --kernel-cmdline \"$(cat {cmdline_path})\" {boot_mount}/EFI/Linux/{efi_name}")


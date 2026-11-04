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
def run(cmd, check=True, env=None, cwd=None, timeout=None, log_cmd=True):
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
        executable="/bin/bash",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=actual_env,
        cwd=cwd,
    )

    full_stdout = []
    full_stderr = []

    def _drain_stdout():
        for line in iter(process.stdout.readline, ""):
            line_clean = line.rstrip("\r\n")
            if line_clean.strip():
                logger.info(line_clean)
            full_stdout.append(line_clean)
        process.stdout.close()

    def _drain_stderr():
        for line in iter(process.stderr.readline, ""):
            line_clean = line.rstrip("\r\n")
            full_stderr.append(line_clean)
        process.stderr.close()

    t_out = threading.Thread(target=_drain_stdout, daemon=True)
    t_err = threading.Thread(target=_drain_stderr, daemon=True)
    t_out.start()
    t_err.start()

    try:
        return_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        t_out.join(timeout=1)
        t_err.join(timeout=1)
        logger.error(f"[TIMEOUT] Command timed out after {timeout}s: {cmd}")
        raise CommandError(cmd, -1, "\n".join(full_stdout), f"Timed out after {timeout}s")

    t_out.join()
    t_err.join()

    stdout_str = "\n".join(full_stdout)
    stderr_str = "\n".join(full_stderr)

    if full_stderr:
        stderr_log = get_stderr_log_path()
        if stderr_log:
            with open(stderr_log, "a", encoding="utf-8") as f:
                f.write(f"\n[CMD] {cmd}\n")
                f.write(stderr_str + "\n")
        else:
            for line in full_stderr:
                if line.strip():
                    logger.warning(f"[STDERR] {line}")

    if check and return_code != 0:
        logger.error(f"[FAIL] {cmd} (exit code: {return_code})")
        if full_stderr:
            for line in full_stderr:
                if line.strip():
                    logger.error(f"[STDERR] {line}")
        raise CommandError(cmd, return_code, stdout_str, stderr_str)

    return Result(stdout_str, stderr_str, return_code)


# -----------------------------------------------------------------------------
# Arch Chroot Wrapper
# -----------------------------------------------------------------------------

def chroot(cmd):
    run(f"""arch-chroot /mnt /bin/bash -e <<'__CHROOT_EOF__'
{cmd}
__CHROOT_EOF__
""")


# -----------------------------------------------------------------------------
# Kernel Parameter Management
# -----------------------------------------------------------------------------

def rebuild_uki(config):
    boot = config.get("boot", {})
    init = boot.get("init", "mkinitcpio")
    kernel = boot.get("kernel", "linux")
    boot_mount = "/efi"
    cmdline_path = "/mnt/etc/kernel/cmdline" if os.path.exists("/mnt/etc/kernel") and os.getuid() == 0 else "/etc/kernel/cmdline"

    logger.info(f"Regenerating UKI (init: {init})")
    if init == "mkinitcpio":
        run("sudo mkinitcpio -P")
    elif init == "dracut":
        efi_name = f"arch-{kernel}.efi"
        run(f"sudo mkdir -p {boot_mount}/EFI/Linux")
        run(f"sudo dracut --uefi --force --hostonly --kernel-cmdline \"$(cat {cmdline_path})\" {boot_mount}/EFI/Linux/{efi_name}")


def apply_kernel_parameter(config, param, rebuild=True):
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
        
        if rebuild:
            rebuild_uki(config)
        return True
    return False


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
    try:
        ans = input("Type 'YES' to proceed: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[ABORTED] Operation cancelled by user.")
        raise RuntimeError("Aborted")
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
    if not os.path.ismount("/mnt"):
        raise RuntimeError("Cannot execute chroot: '/mnt' is not a mountpoint.")
    run(f"""arch-chroot /mnt /bin/bash -e <<'__CHROOT_EOF__'
{cmd}
__CHROOT_EOF__
""")


# -----------------------------------------------------------------------------
# Kernel & UKI Helpers (Delegated to core.kernel for backward compatibility)
# -----------------------------------------------------------------------------

def rebuild_uki(config):
    from core.kernel import rebuild_uki as _rebuild_uki
    return _rebuild_uki(config)


def apply_kernel_parameter(config, param, rebuild=True):
    from core.kernel import apply_kernel_parameter as _apply_kernel_parameter
    return _apply_kernel_parameter(config, param, rebuild=rebuild)


# core/helper_basic.py

import os
import subprocess
import threading
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

def run(cmd, check=True):
    logger.info(f"[CMD] {cmd}")

    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
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

#!/usr/bin/env python3
"""Decrypt age-encrypted config files back to plaintext.

Files decrypted: secrets.yaml.age, laptop_ssh.yaml.age, desktop_ssh.yaml.age
Outputs:         plaintext *.yaml alongside each .age file
"""

import os
import sys
import pty
import fcntl
import termios
import subprocess
import getpass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
SECRETS_DIR = os.path.join(CONFIG_DIR, "secrets")
SSH_DIR = os.path.join(CONFIG_DIR, "ssh")

SENSITIVE_AGE_FILES = [
    os.path.join(SECRETS_DIR, "secrets.yaml.age"),
    os.path.join(SSH_DIR, "laptop.yaml.age"),
    os.path.join(SSH_DIR, "desktop.yaml.age"),
    # Legacy fallbacks
    os.path.join(CONFIG_DIR, "secrets.yaml.age"),
    os.path.join(CONFIG_DIR, "laptop_ssh.yaml.age"),
    os.path.join(CONFIG_DIR, "desktop_ssh.yaml.age"),
]


def _check_age():
    if subprocess.run(["which", "age"], capture_output=True).returncode != 0:
        print("ERROR: age is not installed. Install it with: pacman -S age")
        sys.exit(1)


def _age_run(args, passphrase):
    """Run age with passphrase fed via PTY as the child's controlling terminal."""
    master_fd, slave_fd = pty.openpty()

    def _preexec():
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)

    proc = subprocess.Popen(
        args,
        stdin=slave_fd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=_preexec,
    )
    os.close(slave_fd)
    os.write(master_fd, (passphrase + "\n").encode())
    stdout, stderr = proc.communicate()
    os.close(master_fd)
    return proc.returncode, stdout, stderr


def _decrypt(age_path, passphrase):
    out_path = age_path[:-4]  # strip .age
    rc, _, stderr = _age_run(
        ["age", "--decrypt", "--output", out_path, age_path],
        passphrase,
    )
    if rc != 0:
        raise RuntimeError(stderr.decode().strip())
    return out_path


def main():
    _check_age()

    to_decrypt = [f for f in SENSITIVE_AGE_FILES if os.path.isfile(f)]

    if not to_decrypt:
        print("Nothing to decrypt — no .age files found.")
        sys.exit(0)

    print("Will decrypt:")
    for p in to_decrypt:
        print(f"  {os.path.relpath(p, PROJECT_ROOT)}")
    print()

    passphrase = getpass.getpass("Passphrase: ")

    print()
    decrypted = []
    for age_path in to_decrypt:
        rel = os.path.relpath(age_path, PROJECT_ROOT)
        try:
            out_path = _decrypt(age_path, passphrase)
            print(f"  {rel} → {os.path.relpath(out_path, PROJECT_ROOT)}")
            decrypted.append(age_path)
        except RuntimeError as e:
            print(f"  ERROR decrypting {rel}: {e}")
            sys.exit(1)

    print()
    answer = input("Delete .age files? [y/N] ").strip().lower()
    if answer == "y":
        for path in decrypted:
            os.remove(path)
            print(f"  Deleted {os.path.relpath(path, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()

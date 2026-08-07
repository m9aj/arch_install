# features/ssh.py
# Installs openssh, hardens sshd_config, deploys authorized_keys and optionally a keypair.
# Phase: postreboot (after first reboot).
#
# Server role: enabled on all machines — accepts inbound SSH with pubkey-only auth.
# Client role: enabled on laptop/desktop — deploys keypair so they can SSH out.
# Keys are stored in secrets.yaml (git-ignored, age-encryptable).

import subprocess
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.shell import run
from core.config import get_ssh_path, load_ssh_config
from core.logger import logger

PACMAN_PACKAGES = ["openssh"]


def configure(config, feature):
    ssh_path = get_ssh_path()
    if not os.path.exists(ssh_path):
        logger.warning("[ssh] No ssh config found at %s, skipping", ssh_path)
        return

    cfg = load_ssh_config(ssh_path)
    username = config.get("system", {}).get("username", "ajay")

    _configure_server(cfg.get("server", {}), username)

    client_cfg = cfg.get("client", {})
    if client_cfg.get("private_key"):
        _configure_client(client_cfg, username)


def _configure_server(cfg, username):
    logger.info("[ssh] Configuring sshd")

    run("sudo mkdir -p /etc/ssh/sshd_config.d")

    lines = [
        "PubkeyAuthentication yes",
        "AuthorizedKeysFile .ssh/authorized_keys",
    ]
    if cfg.get("disable_password_auth", True):
        lines += [
            "PasswordAuthentication no",
            "KbdInteractiveAuthentication no",
        ]

    _write_root_file("/etc/ssh/sshd_config.d/10-hardening.conf", "\n".join(lines) + "\n")

    authorized_keys = cfg.get("authorized_keys", [])
    if authorized_keys:
        ssh_dir = f"/home/{username}/.ssh"
        run(f"sudo mkdir -p {ssh_dir}")
        _write_root_file(f"{ssh_dir}/authorized_keys", "\n".join(authorized_keys) + "\n")
        run(f"sudo chmod 700 {ssh_dir}")
        run(f"sudo chmod 600 {ssh_dir}/authorized_keys")
        run(f"sudo chown -R {username}:{username} {ssh_dir}")

    run("sudo systemctl enable --now sshd")
    logger.info("[ssh] sshd enabled and running")


def _configure_client(cfg, username):
    logger.info("[ssh] Deploying SSH keypair")

    ssh_dir = f"/home/{username}/.ssh"
    run(f"sudo mkdir -p {ssh_dir}")

    private_key = cfg.get("private_key", "").strip()
    public_key = cfg.get("public_key", "").strip()

    if private_key:
        path = f"{ssh_dir}/id_ed25519"
        _write_root_file(path, private_key + "\n")
        run(f"sudo chmod 600 {path}")

    if public_key:
        path = f"{ssh_dir}/id_ed25519.pub"
        _write_root_file(path, public_key + "\n")
        run(f"sudo chmod 644 {path}")

    run(f"sudo chown -R {username}:{username} {ssh_dir}")
    logger.info("[ssh] SSH keypair deployed")


def _write_root_file(path, content):
    # Use tee so content is passed via stdin — keeps key material out of the command string.
    proc = subprocess.run(
        ["sudo", "tee", path],
        input=content,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise Exception(f"Failed to write {path}: {proc.stderr.strip()}")

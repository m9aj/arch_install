#!/usr/bin/env python3
"""Generate an ed25519 SSH keypair for a profile and write it to config/{profile}_ssh.yaml.

Usage:
  python3 scripts/gen-ssh-key.py [profile]

If no profile is given, generates for all profiles with ssh client enabled.
The public key is added to config/base_ssh.yaml's authorized_keys list.
"""

import os
import sys
import subprocess
import tempfile
import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
sys.path.insert(0, PROJECT_ROOT)

from core.helper_core import _discover_profiles


def _load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _client_enabled(profile):
    """Return True if this profile has ssh client enabled."""
    features_path = os.path.join(CONFIG_DIR, f"{profile}_features.yaml")
    if not os.path.exists(features_path):
        return False
    data = _load_yaml(features_path)
    return data.get("features", {}).get("ssh", {}).get("config", {}).get("client", {}).get("enabled", False)


def _resolve_profiles():
    profiles = _discover_profiles()
    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        if arg not in profiles:
            print(f"ERROR: unknown profile '{arg}'. Known: {', '.join(profiles)}")
            sys.exit(1)
        return [arg]
    return [p for p in profiles if _client_enabled(p)]


def _get_comment(profile):
    base_core = _load_yaml(os.path.join(CONFIG_DIR, "base_core.yaml"))
    username = base_core.get("system", {}).get("username", "ajay")
    profile_core = _load_yaml(os.path.join(CONFIG_DIR, f"{profile}_core.yaml"))
    hostname = profile_core.get("system", {}).get("hostname", profile)
    return f"{username}@{hostname}"


def _generate_keypair(comment):
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = os.path.join(tmpdir, "id_ed25519")
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-C", comment, "-f", key_path, "-N", ""],
            check=True,
            capture_output=True,
        )
        with open(key_path) as f:
            private_key = f.read()
        with open(key_path + ".pub") as f:
            public_key = f.read().strip()
    return private_key, public_key


def _write_profile_ssh(profile, private_key, public_key, comment):
    path = os.path.join(CONFIG_DIR, f"{profile}_ssh.yaml")
    lines = [
        f"# config/{profile}_ssh.yaml",
        f"# {comment} SSH client keypair.",
        f"# Git-ignored. Encrypt with: age --passphrase -o {profile}_ssh.yaml.age {profile}_ssh.yaml",
        "",
        "client:",
        "  private_key: |",
    ]
    for line in private_key.splitlines():
        lines.append(f"    {line}")
    lines.append(f'  public_key: "{public_key}"')
    lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


def _write_base_ssh(keys):
    """Write base_ssh.yaml with keys as unquoted single-line strings."""
    path = os.path.join(CONFIG_DIR, "base_ssh.yaml")
    lines = [
        "# config/base_ssh.yaml",
        "# Shared SSH server config — authorized_keys apply to all machines.",
        "# This file is committed. Private keys live in {profile}_ssh.yaml[.age] (git-ignored).",
        "",
        "server:",
        "  disable_password_auth: true",
        "  authorized_keys:",
    ]
    for k in keys:
        lines.append(f'    - "{k}"')
    lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))


def _update_base_ssh(public_key, comment):
    """Replace any existing key with the same comment, or append if new."""
    path = os.path.join(CONFIG_DIR, "base_ssh.yaml")
    data = _load_yaml(path)
    keys = [k for k in data.get("server", {}).get("authorized_keys", []) if k]

    # Match by comment (last word of the public key line).
    new_keys = []
    replaced = False
    for k in keys:
        if k.split()[-1] == comment:
            new_keys.append(public_key)
            replaced = True
        else:
            new_keys.append(k)

    if not replaced:
        new_keys.append(public_key)

    _write_base_ssh(new_keys)
    return not replaced  # True = added, False = replaced


def _generate_for_profile(profile):
    comment = _get_comment(profile)
    print(f"Profile : {profile}  ({comment})")

    ssh_yaml = os.path.join(CONFIG_DIR, f"{profile}_ssh.yaml")
    if os.path.exists(ssh_yaml):
        answer = input(f"  config/{profile}_ssh.yaml already exists. Overwrite? [y/N] ").strip().lower()
        if answer != "y":
            print("  Skipped.")
            return

    private_key, public_key = _generate_keypair(comment)

    path = _write_profile_ssh(profile, private_key, public_key, comment)
    print(f"  Written    : {os.path.relpath(path, PROJECT_ROOT)}")

    added = _update_base_ssh(public_key, comment)
    verb = "Added" if added else "Replaced"
    print(f"  {verb:10} : {comment} in config/base_ssh.yaml")
    print(f"  Public key : {public_key}")


def main():
    profiles = _resolve_profiles()
    if not profiles:
        print("No profiles with ssh client enabled found.")
        sys.exit(0)

    for profile in profiles:
        _generate_for_profile(profile)
        print()

    print("Next steps:")
    print("  1. Run scripts/encrypt-secrets.py to encrypt the ssh yaml files")
    print("  2. Commit config/base_ssh.yaml (public keys are not sensitive)")


if __name__ == "__main__":
    main()

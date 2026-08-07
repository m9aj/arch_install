# core/helper_core.py

import sys
import os
import pty
import fcntl
import termios
import subprocess
import yaml
from core.logger import logger

_config_written = False
_dconf_written = False
_ssh_written = False
_passphrase_cache = None

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
PROFILES_DIR = os.path.join(CONFIG_DIR, "profiles")
DCONF_DIR = os.path.join(CONFIG_DIR, "dconf")
SSH_DIR = os.path.join(CONFIG_DIR, "ssh")
SECRETS_DIR = os.path.join(CONFIG_DIR, "secrets")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")

# ------------------------
# Profile detection
# ------------------------

def _discover_profiles():
    """Return all profile names in config/profiles/ (or config/)."""
    target_dir = PROFILES_DIR if os.path.exists(PROFILES_DIR) else CONFIG_DIR
    ignore_files = {
        "base.yaml", "package_profiles.yaml", "wifi.yaml",
        "secrets.yaml", "secrets.yaml.template", "wifi.yaml.template",
        "base_dconf.yaml", "base_ssh.yaml"
    }
    profiles = set()
    for f in os.listdir(target_dir):
        if not f.endswith(".yaml") or f in ignore_files or f.endswith("_dconf.yaml") or f.endswith("_ssh.yaml"):
            continue
        if f.endswith("_core.yaml"):
            profiles.add(f[:-len("_core.yaml")])
        elif f.endswith("_packages.yaml") or f.endswith("_features.yaml") or f.endswith("_config.yaml"):
            continue
        else:
            profiles.add(f[:-len(".yaml")])
    profiles.discard("base")
    return sorted(list(profiles))

def detect_profile():
    """Check for a marker file in the project root named after a known profile."""
    for profile in _discover_profiles():
        if os.path.isfile(os.path.join(PROJECT_ROOT, profile)):
            return profile
    return None

def write_profile_marker(profile):
    """Write a marker file so future runs auto-detect this profile."""
    path = os.path.join(PROJECT_ROOT, profile)
    if not os.path.exists(path):
        open(path, "w").close()

def get_config_path():
    """
    Detect profile from CLI arg or marker file. Sets marker and returns profile name.
    """
    profiles = _discover_profiles()

    if len(sys.argv) >= 2:
        arg = sys.argv[1]

        if arg in profiles:
            write_profile_marker(arg)
            return arg

        print(f"[ERROR] Invalid argument: '{arg}'")
        print(f"        Must be a known profile ({', '.join(profiles)})")
        sys.exit(1)

    profile = detect_profile()
    if profile:
        print(f"[INFO] Using profile from marker file: {profile}")
        return profile

    print(f"Usage: install [{' | '.join(profiles)}]")
    print("       Tip: on first run, specify the profile — a marker file will be")
    print("            created so future runs auto-detect it.")
    sys.exit(1)


def get_dconf_path():
    """Resolve dconf config path: config/dconf/{profile}.yaml or config/{profile}_dconf.yaml."""
    profile = detect_profile()
    if profile:
        new_path = os.path.join(DCONF_DIR, f"{profile}.yaml")
        if os.path.exists(new_path):
            return new_path
        legacy_path = os.path.join(CONFIG_DIR, f"{profile}_dconf.yaml")
        if os.path.exists(legacy_path):
            return legacy_path

    base_new = os.path.join(DCONF_DIR, "base.yaml")
    if os.path.exists(base_new):
        return base_new
    return os.path.join(CONFIG_DIR, "base_dconf.yaml")

def get_ssh_path():
    """Resolve SSH config: config/ssh/{profile}.yaml[.age] or config/{profile}_ssh.yaml[.age]."""
    profile = detect_profile()
    if profile:
        for ext in [".age", ""]:
            new_path = os.path.join(SSH_DIR, f"{profile}.yaml{ext}")
            if os.path.exists(new_path):
                return new_path
            legacy_path = os.path.join(CONFIG_DIR, f"{profile}_ssh.yaml{ext}")
            if os.path.exists(legacy_path):
                return legacy_path

    base_new = os.path.join(SSH_DIR, "base.yaml")
    if os.path.exists(base_new):
        return base_new
    return os.path.join(CONFIG_DIR, "base_ssh.yaml")

# ------------------------
# Config loaders
# ------------------------

def load_yaml(filename):
    path = os.path.join(CONFIG_DIR, filename)
    if not os.path.exists(path) and os.path.exists(os.path.join(PROFILES_DIR, filename)):
        path = os.path.join(PROFILES_DIR, filename)
    with open(path) as f:
        return yaml.safe_load(f)

def load_wifi_bootstrap():
    """Load wifi.yaml directly — no age decryption needed."""
    for dir_path in [SECRETS_DIR, CONFIG_DIR]:
        path = os.path.join(dir_path, "wifi.yaml")
        if os.path.exists(path):
            with open(path) as f:
                return yaml.safe_load(f) or {}
    return {}

def merge_dicts(base, override):
    result = base.copy()

    for k, v in override.items():
        if k in base:
            if isinstance(v, dict) and isinstance(base[k], dict):
                result[k] = merge_dicts(base[k], v)
            elif isinstance(v, list) and isinstance(base[k], list):
                # Smart merge for lists of dicts with a 'name' key (e.g., subvolumes)
                if v and all(isinstance(i, dict) and 'name' in i for i in v) and \
                   base[k] and all(isinstance(i, dict) and 'name' in i for i in base[k]):

                    merged_list = list(base[k])
                    for override_item in v:
                        match = next((item for item in merged_list if item.get('name') == override_item.get('name')), None)
                        if match:
                            idx = merged_list.index(match)
                            merged_list[idx] = merge_dicts(match, override_item)
                        else:
                            merged_list.append(override_item)
                    result[k] = merged_list
                else:
                    result[k] = base[k] + v
            else:
                result[k] = v
        else:
            result[k] = v

    return result

_SECRET_KEYS = {"root_password", "user_password", "password"}

def _redact(obj):
    """Recursively replace known secret keys with *** for safe debug logging."""
    if isinstance(obj, dict):
        return {k: "***" if k in _SECRET_KEYS else _redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(i) for i in obj]
    return obj

def _decrypt_age_yaml(path):
    """Decrypt an age-encrypted YAML file, prompting for passphrase once and caching it."""
    global _passphrase_cache
    if _passphrase_cache is None:
        import getpass
        _passphrase_cache = getpass.getpass("Age passphrase: ")

    master_fd, slave_fd = pty.openpty()

    def _preexec():
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)

    proc = subprocess.Popen(
        ["age", "--decrypt", path],
        stdin=slave_fd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=_preexec,
    )
    os.close(slave_fd)
    os.write(master_fd, (_passphrase_cache + "\n").encode())
    stdout, stderr = proc.communicate()
    os.close(master_fd)
    if proc.returncode != 0:
        _passphrase_cache = None
        raise RuntimeError(f"age decryption failed for {path}: {stderr.decode().strip()}")
    return yaml.safe_load(stdout.decode())

def load_profile_config(profile):
    """
    Load and merge all config files for a profile.

    Merge precedence:
      1. Base config: config/profiles/base.yaml (or config/base.yaml)
      2. Profile config: config/profiles/{profile}.yaml (or config/{profile}.yaml)
      3. Plain wifi.yaml (config/secrets/wifi.yaml)
      4. Secrets (config/secrets/secrets.yaml[.age])
    """
    config = {}

    # 1. Base configuration
    base_consolidated = os.path.join(PROFILES_DIR, "base.yaml")
    if not os.path.exists(base_consolidated):
        base_consolidated = os.path.join(CONFIG_DIR, "base.yaml")
    if os.path.exists(base_consolidated):
        with open(base_consolidated) as f:
            config = yaml.safe_load(f) or {}

    # 2. Profile overrides
    profile_consolidated = os.path.join(PROFILES_DIR, f"{profile}.yaml")
    if not os.path.exists(profile_consolidated):
        profile_consolidated = os.path.join(CONFIG_DIR, f"{profile}.yaml")
    if os.path.exists(profile_consolidated):
        with open(profile_consolidated) as f:
            override = yaml.safe_load(f) or {}
        config = merge_dicts(config, override)

    # 3. Wifi config
    for wifi_dir in [SECRETS_DIR, CONFIG_DIR]:
        wifi_path = os.path.join(wifi_dir, "wifi.yaml")
        if os.path.exists(wifi_path):
            with open(wifi_path) as f:
                wifi = yaml.safe_load(f) or {}
            config = merge_dicts(config, wifi)
            break

    # 4. Secrets
    secrets_found = False
    for sec_dir in [SECRETS_DIR, CONFIG_DIR]:
        age_path = os.path.join(sec_dir, "secrets.yaml.age")
        plain_path = os.path.join(sec_dir, "secrets.yaml")
        if os.path.exists(age_path):
            secrets = _decrypt_age_yaml(age_path)
            secrets_found = True
        elif os.path.exists(plain_path):
            with open(plain_path) as f:
                secrets = yaml.safe_load(f) or {}
            secrets_found = True
        else:
            secrets = {}
        if secrets_found:
            config = merge_dicts(config, secrets)
            break

    global _config_written
    if not _config_written:
        os.makedirs(LOGS_DIR, exist_ok=True)
        merged_path = os.path.join(LOGS_DIR, "merged_config.yaml")
        with open(merged_path, "w") as f:
            yaml.dump(_redact(config), f, default_flow_style=False)
        _config_written = True

    return config

def load_dconf(path):
    """Load dconf config, merging base dconf config with the profile-specific file."""
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}

    base_path = os.path.join(DCONF_DIR, "base.yaml")
    if not os.path.exists(base_path):
        base_path = os.path.join(CONFIG_DIR, "base_dconf.yaml")

    if os.path.abspath(path) != os.path.abspath(base_path) and os.path.exists(base_path):
        with open(base_path) as f:
            base = yaml.safe_load(f) or {}
        cfg = merge_dicts(base, cfg)

    global _dconf_written
    if not _dconf_written:
        os.makedirs(LOGS_DIR, exist_ok=True)
        merged_path = os.path.join(LOGS_DIR, "merged_dconf.yaml")
        with open(merged_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False)
        _dconf_written = True

    return cfg

def load_ssh_config(path):
    """Load SSH config, merging base SSH config with the profile-specific file (supports .age)."""
    if path.endswith(".age"):
        cfg = _decrypt_age_yaml(path)
    else:
        with open(path) as f:
            cfg = yaml.safe_load(f) or {}

    base_path = os.path.join(SSH_DIR, "base.yaml")
    if not os.path.exists(base_path):
        base_path = os.path.join(CONFIG_DIR, "base_ssh.yaml")

    if os.path.abspath(path) != os.path.abspath(base_path) and os.path.exists(base_path):
        with open(base_path) as f:
            base = yaml.safe_load(f) or {}
        cfg = merge_dicts(base, cfg)

    global _ssh_written
    if not _ssh_written:
        os.makedirs(LOGS_DIR, exist_ok=True)
        merged_path = os.path.join(LOGS_DIR, "merged_ssh.yaml")
        with open(merged_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False)
        _ssh_written = True

    return cfg

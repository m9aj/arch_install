# postreboot/gnome_config.py
# GNOME configuration: gsettings (dconf) + app drawer (hide, folders, dock).
# All functions are no-ops when arch.de != gnome.

import json
import os
import shlex
import tempfile
import urllib.request
from core.helper_core import load_yaml, detect_profile, load_dconf, get_dconf_path
from core.helper_basic import run
from core.helper_gnome import _is_gnome, normalize_desktop_name
from core.logger import logger


# ------------------------
# gsettings / dconf
# ------------------------

def apply_gsettings(config):
    if not _is_gnome(config):
        return False

    cfg = config.get("postconfig", {}).get("gnome", {}).get("gsettings", {})
    if not cfg.get("enabled"):
        return False

    # 1. Resolve dconf config path
    dconf_path = get_dconf_path()
    
    if not os.path.exists(dconf_path):
        logger.warning(f"No dconf configuration found at {dconf_path}")
        return False

    # 2. Load settings (inheritance and logging handled by load_dconf)
    logger.info(f"Loading dconf settings from {dconf_path}")
    gsettings = load_dconf(dconf_path)
    
    # Remove 'extends' if present so it doesn't get processed as a schema
    gsettings.pop("extends", None)

    logger.info("Applying GNOME settings")

    for schema, keys in gsettings.items():
        for key, value in keys.items():
            # Handle list/string quoting for gsettings (GVariant format)
            if isinstance(value, list):
                val_str = "[" + ", ".join(f"'{v}'" for v in value) + "]"
            elif isinstance(value, str) and not (value.startswith("'") or value.startswith('"') or value in ["true", "false"]):
                # Escape chars that would break outer double-quote shell context
                escaped = value.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
                val_str = f"'{escaped}'"
            else:
                val_str = str(value)

            run(f"gsettings set {schema} {key} \"{val_str}\"", check=False)


# ------------------------
# Extensions
# ------------------------

def install_gnome_extensions(config):
    if not _is_gnome(config):
        return False

    cfg = config.get("postconfig", {}).get("gnome", {}).get("extensions", {})
    if not cfg.get("enabled"):
        return False

    ids = cfg.get("ids", [])
    if not ids:
        return False

    result = run("gnome-shell --version", check=False)
    if result.returncode != 0:
        logger.warning("Could not determine GNOME Shell version — skipping extensions")
        return False
    shell_version = result.stdout.strip().split()[-1]
    logger.info(f"Installing {len(ids)} GNOME extensions for Shell {shell_version}")

    failures = []
    installed_uuids = []
    for ext_id in ids:
        try:
            uuid = _install_extension(ext_id, shell_version)
            installed_uuids.append(uuid)
        except Exception as e:
            logger.warning(f"Extension {ext_id}: {e}")
            failures.append(ext_id)

    if installed_uuids:
        uuid_list = "[" + ",".join(f"'{u}'" for u in installed_uuids) + "]"
        run(f"gsettings set org.gnome.shell enabled-extensions \"{uuid_list}\"", check=False)
        logger.info(f"Pre-enabled {len(installed_uuids)} extensions via gsettings")

    return failures if failures else True


def _install_extension(ext_id, shell_version):
    url = f"https://extensions.gnome.org/extension-info/?pk={ext_id}&shell_version={shell_version}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            info = json.loads(resp.read())
    except Exception:
        raise RuntimeError(f"not found or incompatible with Shell {shell_version}")

    uuid = info.get("uuid")
    download_url = info.get("download_url")
    if not uuid or not download_url:
        raise RuntimeError("missing uuid or download_url in API response")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        tmp_path = f.name

    try:
        urllib.request.urlretrieve(f"https://extensions.gnome.org{download_url}", tmp_path)
        result = run(f"gnome-extensions install --force {shlex.quote(tmp_path)}", check=False)
        if result.returncode != 0:
            raise RuntimeError("gnome-extensions install failed")
        logger.info(f"Installed: {uuid}")
    finally:
        os.unlink(tmp_path)
    return uuid


# ------------------------
# Custom keybindings
# ------------------------

def apply_custom_keybindings(config):
    if not _is_gnome(config):
        return False

    cfg = config.get("postconfig", {}).get("gnome", {}).get("keybindings", {})
    if not cfg.get("enabled"):
        return False

    bindings = cfg.get("bindings", [])
    if not bindings:
        return False

    base = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
    schema = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"

    logger.info("Applying custom keybindings")

    paths = [f"{base}/custom{i}/" for i in range(len(bindings))]
    path_list = "[" + ", ".join(f"'{p}'" for p in paths) + "]"
    run(f"gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings \"{path_list}\"")

    for i, kb in enumerate(bindings):
        path = paths[i]
        for field in ("name", "command", "binding"):
            escaped = kb[field].replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
            run(f"gsettings set {schema}:{path} {field} \"'{escaped}'\"")


# ------------------------
# App drawer
# ------------------------

def hide_apps(config):
    if not _is_gnome(config):
        return False

    cfg = config.get("postconfig", {}).get("gnome", {}).get("appdrawer", {})
    if not cfg.get("enabled"):
        return False

    apps = cfg.get("hide_apps", [])
    if not apps:
        return False

    user = config["system"]["username"]
    user_dir = f"/home/{user}/.local/share/applications"

    logger.info("Hiding GNOME apps")
    run(f"mkdir -p {shlex.quote(user_dir)}")

    for name in apps:
        app = normalize_desktop_name(name)
        src = f"/usr/share/applications/{app}"
        dst = f"{user_dir}/{app}"

        if not os.path.exists(src):
            logger.warning(f"App not found: {app}")
            continue

        run(f"cp {shlex.quote(src)} {shlex.quote(dst)}")
        run(f"grep -q 'NoDisplay=true' {shlex.quote(dst)} || echo 'NoDisplay=true' >> {shlex.quote(dst)}")


def dash_folders(config):
    if not _is_gnome(config):
        return False

    cfg = config.get("postconfig", {}).get("gnome", {}).get("appdrawer", {})
    if not cfg.get("enabled"):
        return False

    folders = cfg.get("folders", {})
    if not folders:
        return False

    logger.info("Applying GNOME app folders")

    folder_names = list(folders.keys())
    folder_list = "[" + ", ".join(f"'{f}'" for f in folder_names) + "]"
    run(f"gsettings set org.gnome.desktop.app-folders folder-children \"{folder_list}\"")

    for folder, apps in folders.items():
        path = f"/org/gnome/desktop/app-folders/folders/{folder}/"
        run(f"gsettings set org.gnome.desktop.app-folders.folder:{path} name '{folder}'")

        app_list = [normalize_desktop_name(a) for a in apps]
        app_str = "[" + ", ".join(f"'{a}'" for a in app_list) + "]"
        run(f"gsettings set org.gnome.desktop.app-folders.folder:{path} apps \"{app_str}\"")


def apply_gnome_dock(config):
    if not _is_gnome(config):
        return False

    cfg = config.get("postconfig", {}).get("gnome", {}).get("appdrawer", {})
    if not cfg.get("enabled"):
        return False

    dock = cfg.get("dock", [])
    if not dock:
        return False

    logger.info("Setting GNOME dock apps")

    apps = [normalize_desktop_name(a) for a in dock]
    app_str = "[" + ", ".join(f"'{a}'" for a in apps) + "]"
    run(f"gsettings set org.gnome.shell favorite-apps \"{app_str}\"")


def apply_app_picker_layout(config):
    if not _is_gnome(config):
        return False

    cfg = config.get("postconfig", {}).get("gnome", {}).get("appdrawer", {})
    if not cfg.get("enabled"):
        return False

    layout = cfg.get("layout", [])
    if not layout:
        return False

    logger.info("Applying GNOME app picker layout")

    # GNOME expects: [{'app1': <{'position': <0>}>}, {'folder1': <{'position': <1>}>}]
    pages_str = []
    for page in layout:
        items = []
        for i, item in enumerate(page):
            # If it doesn't look like a desktop file, it's likely a folder name
            name = normalize_desktop_name(item) if "." in item else item
            items.append(f"'{name}': <{{'position': <{i}>}}>")
        pages_str.append("{" + ", ".join(items) + "}")

    gvariant_str = "[" + ", ".join(pages_str) + "]"
    run(f"gsettings set org.gnome.shell app-picker-layout \"{gvariant_str}\"")


def apply_color_profiles(config):
    if not _is_gnome(config):
        return False

    cfg = config.get("postconfig", {}).get("gnome", {}).get("color_profiles", {})
    if not cfg.get("enabled"):
        return False

    profiles = cfg.get("profiles", [])
    if not profiles:
        return False

    logger.info("Applying GNOME color profiles")

    for cp in profiles:
        profile_path = cp.get("file")
        if not profile_path or not os.path.exists(profile_path):
            logger.warning(f"Color profile file not found: {profile_path}")
            continue

        filename = os.path.basename(profile_path)

        # 1. Import profile
        run(f"colormgr import-profile {shlex.quote(profile_path)}", check=False)

        # 2. Get primary device ID
        cmd_get_device = "colormgr get-devices | grep -B 15 'OutputPriority=primary' | grep 'Device ID:' | awk '{print $3}'"
        device_id = run(cmd_get_device, check=False).stdout.strip()

        if not device_id:
            logger.warning("Could not find primary device ID for color profile")
            continue

        # 3. Get profile ID
        profile_id = run(
            f"colormgr --value-only find-profile-by-filename {shlex.quote(filename)} | grep 'icc-'",
            check=False,
        ).stdout.strip()

        if not profile_id:
            logger.warning(f"Could not find profile ID for {filename}")
            continue

        # 4. Add and set as default
        logger.info(f"Adding profile {profile_id} to device {device_id}")
        run(f"colormgr device-add-profile {shlex.quote(device_id)} {shlex.quote(profile_id)}", check=False)
        run(f"colormgr device-make-profile-default {shlex.quote(device_id)} {shlex.quote(profile_id)}", check=False)

    return True


def apply_lockscreen_config(config):
    """Copies user's monitors.xml to /etc/xdg so the GDM lock screen matches user layout."""
    if not _is_gnome(config):
        return False

    cfg = config.get("postconfig", {}).get("gnome", {}).get("lockscreen_scaling", {})
    if not cfg.get("enabled"):
        return False

    user = config["system"]["username"]
    src = f"/home/{user}/.config/monitors.xml"
    dst = "/etc/xdg/monitors.xml"

    if not os.path.exists(src):
        logger.warning(f"No monitors.xml found at {src}")
        return False

    logger.info("Applying monitor configuration to /etc/xdg")
    run(f"sudo cp {shlex.quote(src)} {dst}")
    run(f"sudo chmod 644 {dst}")

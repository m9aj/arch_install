# postreboot/main.py
# Post-reboot — run as regular user after first boot.
# Covers system setup and GNOME config in a single pass.

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_core import get_config_path, load_profile_config, LOGS_DIR
from core.helper_basic import set_stderr_log
from core.validator import validate
from core.state import is_done, mark_done, mark_skipped, mark_failed
from core.logger import logger, setup as setup_logger
from core import helper_network as network

from postreboot import (
    aur, home_shortcuts, features, dotfiles,
    config_steps, gnome_config, themes
)
from features import local_aur_repo

STEPS = [
    ("home_shortcuts",        home_shortcuts.setup_user_dirs),
    ("dotfiles",              dotfiles.setup_dotfiles),
    ("bluetooth",             dotfiles.setup_bluetooth),
    ("network_hosts",          network.apply_static_hosts),
    ("local_aur_repo_client", local_aur_repo.configure_client),
    ("aur_helper",            aur.install_aur_helper),
    ("features",        features.run_enabled_features),
    ("aur_packages",    aur.install_aur_packages),
    ("gsettings",       gnome_config.apply_gsettings),
    ("lockscreen_config", gnome_config.apply_lockscreen_config),
    ("extensions",      gnome_config.install_gnome_extensions),
    ("keybindings",     gnome_config.apply_custom_keybindings),
    ("hide_apps",       gnome_config.hide_apps),
    ("app_folders",     gnome_config.dash_folders),
    ("dock",            gnome_config.apply_gnome_dock),
    ("color_profiles",  gnome_config.apply_color_profiles),
    ("themes",          themes.install_themes),
    ("citrix",          config_steps.configure_citrix),
    ("app_layout",      gnome_config.apply_app_picker_layout),
]


def main():
    setup_logger(os.path.join(LOGS_DIR, "postreboot.log"))
    set_stderr_log(os.path.join(LOGS_DIR, "postreboot_err.log"))

    if os.getuid() == 0:
        print("[ERROR] Phase 2 must NOT be run as root.")
        print("Run as your regular user — sudo is used internally when needed.")
        sys.exit(1)

    profile = get_config_path()
    config = load_profile_config(profile)

    logger.info(f"Using profile: {profile}")

    validate(config)

    logger.info("Checking for internet connection...")
    network.ensure_internet(config)

    for name, func in STEPS:
        if not is_done(name):
            logger.info(f"Running step: {name}")
            try:
                result = func(config)
                if result is False:
                    logger.info(f"Step '{name}' skipped (disabled in config)")
                    mark_skipped(name)
                else:
                    if isinstance(result, list) and result:
                        logger.warning(f"Step '{name}' completed with failures: {result}")
                    mark_done(name)
            except Exception as e:
                logger.error(f"Step '{name}' failed: {e}")
                mark_failed(name)
                raise
        else:
            logger.info(f"Skipping {name}, already done or skipped")


if __name__ == "__main__":
    main()

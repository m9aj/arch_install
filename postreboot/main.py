# postreboot/main.py
# Post-reboot — run as regular user after first boot.
# Covers system setup and GNOME config in a single pass.

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.config import get_config_path, load_profile_config, LOGS_DIR
from core.shell import run
from core.validator import validate
from core.state import is_done, mark_done, mark_skipped, mark_failed
from core.logger import logger, setup as setup_logger, set_stderr_log

from core import network

from postreboot import (
    aur, user_dirs, features, dotfiles,
    system_config, gnome, themes
)
from features import local_aur_repo

STEPS = [
    ("user_dirs",             user_dirs.setup_user_dirs),
    ("dotfiles",              dotfiles.setup_dotfiles),
    ("bluetooth",             dotfiles.setup_bluetooth),
    ("network_hosts",          system_config.apply_static_hosts),
    ("local_aur_repo_client", local_aur_repo.configure_client),
    ("aur_helper",            aur.install_aur_helper),
    ("features",              features.run_enabled_features),

    ("aur_packages",          aur.install_aur_packages),
    ("gsettings",             gnome.apply_gsettings),
    ("lockscreen_config",     gnome.apply_lockscreen_config),
    ("extensions",            gnome.install_gnome_extensions),
    ("keybindings",           gnome.apply_custom_keybindings),
    ("hide_apps",             gnome.hide_apps),
    ("app_folders",           gnome.dash_folders),
    ("dock",                  gnome.apply_gnome_dock),
    ("color_profiles",        gnome.apply_color_profiles),
    ("themes",                themes.install_themes),
    ("citrix",                system_config.configure_citrix),
    ("app_layout",            gnome.apply_app_picker_layout),
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
    while True:
        try:
            network.ensure_internet(config)
            break
        except RuntimeError as e:
            logger.warning(f"Internet check failed: {e}")
            print("\n[WARNING] No internet connection detected.")
            print("This phase requires an active internet connection to download packages and apply settings.")
            print("Please connect to the internet.")
            try:
                response = input("Press Enter to retry, or type 'q' to quit: ").strip().lower()
                if response == 'q':
                    logger.info("User chose to exit because of no internet connection.")
                    sys.exit(1)
            except (KeyboardInterrupt, EOFError):
                print()
                logger.info("Exiting on user interrupt.")
                sys.exit(1)

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

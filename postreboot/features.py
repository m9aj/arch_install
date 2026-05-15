# postreboot/features.py
# Dynamic feature runner — iterates enabled features in config and executes
# their respective scripts in the features/ directory.

import importlib
from core.state import is_done, mark_done, mark_failed, mark_skipped
from core.logger import logger
from core.helper_basic import run
from core.helper_installer import install_packages

def run_enabled_features(config):
    """
    Main entry point for Phase 2 features.
    Iterates through config['features'], discovers metadata from feature modules,
    installs packages, and runs custom configuration.
    Each feature module is responsible for enabling its own services.
    """
    features = config.get("features", {})

    any_enabled = False
    for name, feature in features.items():
        state_key = f"feature.{name}"
        # Features with server/client roles use server.enabled; others use top-level enabled.
        server_block = feature.get("server")
        enabled = server_block.get("enabled", False) if server_block is not None else feature.get("enabled", False)
        if not enabled:
            if not is_done(state_key):
                logger.info(f"[SKIP] Feature {name} is disabled in config")
                mark_skipped(state_key)
            continue

        any_enabled = True
        if is_done(state_key):
            logger.info(f"[SKIP] Feature: {name} (already done/skipped)")
            continue

        logger.info(f"--- [FEATURE: {name}] ---")
        
        # Dynamically import the module to get its metadata
        try:
            module = importlib.import_module(f"features.{name}")
        except ImportError:
            logger.error(f"[{name}] No custom handler script found (features/{name}.py)")
            mark_failed(state_key)
            continue

        # 1. Install Pacman and AUR Packages
        pacman_pkgs = getattr(module, "PACMAN_PACKAGES", [])
        aur_pkgs = getattr(module, "AUR_PACKAGES", [])

        if pacman_pkgs or aur_pkgs:
            logger.info(f"[{name}] Installing packages")
            try:
                install_packages(config, pacman_pkgs=pacman_pkgs, aur_pkgs=aur_pkgs)
            except Exception as e:
                logger.error(f"[{name}] Error installing packages: {e}")
                mark_failed(state_key)
                continue

        # 2. Run Custom Configuration Logic
        try:
            if hasattr(module, "configure"):
                logger.info(f"[{name}] Running custom configuration handler")
                module.configure(config, feature)
            else:
                logger.info(f"[{name}] No configure() function found")
        except Exception as e:
            logger.error(f"[{name}] Error during configuration: {e}")
            mark_failed(state_key)
            continue

        mark_done(state_key)
        logger.info(f"--- [DONE: {name}] ---\n")

    if not any_enabled:
        return False

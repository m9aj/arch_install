# postreboot/hyprland.py
# Hyprland & Quickshell desktop environment deployment.
# All functions are no-ops when hyprland is not enabled in arch.de.

import os
import shutil
from core.config import PROJECT_ROOT
from core.shell import run
from core.gnome import _is_hyprland
from core.logger import logger


def setup_hyprland(config):
    """Entrypoint called by postreboot/main.py."""
    if not _is_hyprland(config):
        return False

    logger.info("[HYPRLAND] Setting up Hyprland and Quickshell desktop environment...")

    user = config["system"]["username"]
    home = f"/home/{user}"
    assets_dir = os.path.join(PROJECT_ROOT, "assets", "hyprland")

    # 1. Deploy Hyprland configuration
    hypr_cfg_dir = os.path.join(home, ".config", "hypr")
    os.makedirs(hypr_cfg_dir, exist_ok=True)
    src_hypr_dir = os.path.join(assets_dir, "hypr")
    if os.path.exists(src_hypr_dir):
        run(f"cp -rT '{src_hypr_dir}' '{hypr_cfg_dir}'")
        logger.info(f"[HYPRLAND] Deployed Hyprland configuration to {hypr_cfg_dir}")

    # 2. Deploy Omarchy components (shell, default configs, themes, bin)
    omarchy_dir = os.path.join(home, ".local", "share", "omarchy")
    omarchy_src = os.path.join(assets_dir, "omarchy")
    if os.path.exists(omarchy_src):
        os.makedirs(omarchy_dir, exist_ok=True)
        run(f"cp -rT '{omarchy_src}' '{omarchy_dir}'")
        bin_dst = os.path.join(omarchy_dir, "bin")
        if os.path.exists(bin_dst):
            run(f"chmod +x '{bin_dst}'/*")
        logger.info(f"[HYPRLAND] Deployed Omarchy components to {omarchy_dir}")

    # Deploy standalone helper binaries to ~/.local/bin
    local_bin_dir = os.path.join(home, ".local", "bin")
    os.makedirs(local_bin_dir, exist_ok=True)
    for script in ["screenshot", "ocr-snip", "qr-scan", "toggle-bar", "toggle-nightlight", "toggle-stay-awake", "toggle-dnd", "open-web", "edit-config", "launch"]:
        s_src = os.path.join(assets_dir, "omarchy", "bin", script)
        s_dst = os.path.join(local_bin_dir, script)
        if os.path.exists(s_src):
            shutil.copy2(s_src, s_dst)
            os.chmod(s_dst, 0o755)
    logger.info(f"[HYPRLAND] Deployed standalone scripts to {local_bin_dir}")

    # Symlink ~/.config/quickshell -> ~/.local/share/omarchy/shell
    shell_dst = os.path.join(omarchy_dir, "shell")
    qs_cfg_link = os.path.join(home, ".config", "quickshell")
    if not os.path.exists(qs_cfg_link) and not os.path.islink(qs_cfg_link):
        os.symlink(shell_dst, qs_cfg_link)
        logger.info(f"[HYPRLAND] Created symlink {qs_cfg_link} -> {shell_dst}")

    # Deploy shell.json to ~/.config/omarchy/shell.json
    omarchy_cfg_dir = os.path.join(home, ".config", "omarchy")
    os.makedirs(omarchy_cfg_dir, exist_ok=True)
    shell_json_src = os.path.join(omarchy_src, "shell", "shell.json")
    shell_json_dst = os.path.join(omarchy_cfg_dir, "shell.json")
    if os.path.exists(shell_json_src) and not os.path.exists(shell_json_dst):
        shutil.copy2(shell_json_src, shell_json_dst)
        logger.info(f"[HYPRLAND] Initialized {shell_json_dst}")

    # Initialize screensaver branding
    branding_dir = os.path.join(omarchy_cfg_dir, "branding")
    os.makedirs(branding_dir, exist_ok=True)
    branding_src = os.path.join(omarchy_src, "logo.txt")
    branding_dst = os.path.join(branding_dir, "screensaver.txt")
    if os.path.exists(branding_src) and not os.path.exists(branding_dst):
        shutil.copy2(branding_src, branding_dst)
        logger.info(f"[HYPRLAND] Initialized screensaver branding at {branding_dst}")

    # 3. Deploy Antigravity Custom Skill
    skill_src = os.path.join(assets_dir, "skills", "hyprland-pilot", "SKILL.md")
    skill_dst_dir = os.path.join(home, ".gemini", "antigravity-cli", "skills", "hyprland-pilot")
    if os.path.exists(skill_src):
        os.makedirs(skill_dst_dir, exist_ok=True)
        shutil.copy2(skill_src, os.path.join(skill_dst_dir, "SKILL.md"))
        logger.info(f"[HYPRLAND] Deployed Antigravity skill to {skill_dst_dir}")

    # Deploy Satty screenshot editor configuration
    satty_cfg_dir = os.path.join(home, ".config", "satty")
    os.makedirs(satty_cfg_dir, exist_ok=True)
    satty_src = os.path.join(assets_dir, "satty", "config.toml")
    satty_dst = os.path.join(satty_cfg_dir, "config.toml")
    if os.path.exists(satty_src) and not os.path.exists(satty_dst):
        shutil.copy2(satty_src, satty_dst)
        logger.info(f"[HYPRLAND] Deployed satty configuration to {satty_dst}")

    # 4. Apply initial theme
    chosen_theme = config.get("postconfig", {}).get("hyprland", {}).get("theme", "tokyo-night")
    theme_script = os.path.join(bin_dst, "omarchy-theme-set")
    if os.path.exists(theme_script):
        logger.info(f"[HYPRLAND] Applying default theme: {chosen_theme}")
        run(f"sudo -H -u {user} env OMARCHY_PATH='{omarchy_dir}' PATH='{bin_dst}':$PATH bash '{theme_script}' '{chosen_theme}'", check=False)

    # 5. Enforce User Ownership
    run(f"chown -R {user}:{user} '{home}/.config/hypr' '{home}/.config/omarchy' '{home}/.config/satty' '{local_bin_dir}' '{omarchy_dir}' '{home}/.config/quickshell'")

    logger.info("[HYPRLAND] Setup completed successfully.")
    return True

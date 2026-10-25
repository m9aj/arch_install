---
name: arch-install-pilot
description: >
  Guide for maintaining, synchronizing, and updating the Arch Linux automated installer repository
  at /home/ajay/Projects/arch_install. Use this skill when synchronizing live system changes
  (installed packages, /etc configurations, network hosts, GNOME/Hyprland desktop settings,
  services, or dotfiles) into the installer configs, profiles, and assets.
---

# Arch Install Pilot Skill

This skill guides the AI assistant in synchronizing live system modifications into the
`arch_install` repository (`/home/ajay/Projects/arch_install`), ensuring that changes made to the
active machine can be reproduced on fresh installations or other systems (laptop, desktop, server).

---

## 1. Repository Architecture & File Mapping

When synchronizing system changes, identify which subsystem changed and update the corresponding file in `arch_install`:

| System Subsystem | Live System Change | Repository Target File | Key / Location |
| :--- | :--- | :--- | :--- |
| **Global Packages** | Installed pacman / AUR tool intended for all desktop profiles | [`config/package_profiles.yaml`](file:///home/ajay/Projects/arch_install/config/package_profiles.yaml) | Under relevant category (`base`, `development`, `desktop_environment`, `multimedia`, etc.) |
| **Machine Packages** | Packages specific to one machine (laptop, desktop, or server) | [`config/profiles/{laptop,desktop,server}.yaml`](file:///home/ajay/Projects/arch_install/config/profiles/) | Under `machine_specific.pacman` or `machine_specific.aur` |
| **Network Hosts** | `/etc/hosts` additions or IP address updates | [`config/profiles/{laptop,desktop,base}.yaml`](file:///home/ajay/Projects/arch_install/config/profiles/) | Under `network.hosts:` (e.g. `media.local: 192.168.40.100`) |
| **Local AUR Repo** | AUR build server / client IP (Tailscale vs LAN) | [`config/profiles/base.yaml`](file:///home/ajay/Projects/arch_install/config/profiles/base.yaml) | Under `features.local_aur_repo.client.config.{tailscale_ip,lan_ip}` |
| **Hidden GNOME Apps** | Apps hidden from launcher (`NoDisplay=true` in `~/.local/share/applications/`) | [`config/profiles/base.yaml`](file:///home/ajay/Projects/arch_install/config/profiles/base.yaml) | Under `postconfig.gnome.appdrawer.hide_apps` |
| **GNOME Dock** | Favorite apps pinned to the dock | [`config/profiles/{base,laptop,desktop}.yaml`](file:///home/ajay/Projects/arch_install/config/profiles/) | Under `postconfig.gnome.appdrawer.dock` |
| **GNOME Folders** | App grid folders & grouped apps | [`config/profiles/base.yaml`](file:///home/ajay/Projects/arch_install/config/profiles/base.yaml) | Under `postconfig.gnome.appdrawer.folders` |
| **GNOME Extensions** | Installed GNOME Shell extensions | [`config/profiles/base.yaml`](file:///home/ajay/Projects/arch_install/config/profiles/base.yaml) | Under `postconfig.gnome.extensions.ids` (extension IDs from extensions.gnome.org) |
| **GNOME dconf** | Settings via `gsettings set` or `dconf write` | [`config/dconf/{base,laptop,desktop}.yaml`](file:///home/ajay/Projects/arch_install/config/dconf/) | Under the corresponding schema and key |
| **Hyprland Lua** | Compositor rules, binds, animations | [`assets/hyprland/hypr/hyprland.lua`](file:///home/ajay/Projects/arch_install/assets/hyprland/hypr/hyprland.lua) | Mirror changes from `~/.config/hypr/hyprland.lua` |
| **Top Bar / Quickshell** | Bar layout, styling, font size | [`assets/hyprland/omarchy/shell.toml`](file:///home/ajay/Projects/arch_install/assets/hyprland/omarchy/shell.toml) | Mirror changes from `~/.config/omarchy/shell.toml` |
| **Launcher Menu** | Omarchy application launcher routes/items | [`assets/hyprland/omarchy/default/omarchy/omarchy-menu.jsonc`](file:///home/ajay/Projects/arch_install/assets/hyprland/omarchy/default/omarchy/omarchy-menu.jsonc) | Mirror changes from `~/.local/share/omarchy/default/omarchy/omarchy-menu.jsonc` |
| **System Features** | Enabling/disabling firewall, zram, tailscale, snapper, btrfs maintenance | [`config/profiles/{base,laptop,desktop,server}.yaml`](file:///home/ajay/Projects/arch_install/config/profiles/) | Under `features.<feature_name>.enabled` |

---

## 2. Sync Procedures & Best Practices

1. **Check Scope (Global vs. Machine-Specific):**
   - If a change is common to all personal machines (e.g. general utility packages, standard hidden apps, core dconf settings), update [`config/profiles/base.yaml`](file:///home/ajay/Projects/arch_install/config/profiles/base.yaml) or [`config/package_profiles.yaml`](file:///home/ajay/Projects/arch_install/config/package_profiles.yaml).
   - If a change is specific to hardware or machine role (e.g. Bluetooth toggle, GPU drivers, battery/touchpad settings, specific network IPs), place it in the target machine profile (`laptop.yaml`, `desktop.yaml`, or `server.yaml`).

2. **Verify Desktop File Application IDs:**
   - GNOME uses reverse-domain desktop IDs (e.g. `com.mitchellh.ghostty`, `org.gnome.FileRoller`). Check `/usr/share/applications/` to confirm exact names when configuring `hide_apps`, `dock`, or `folders`.

3. **Validate Config Syntax:**
   - After updating YAML files, verify valid syntax with `python3 -c "import yaml; yaml.safe_load(open('path/to/file.yaml'))"`.
   - After updating Python modules, verify with `python3 -m py_compile path/to/script.py`.

4. **Git Workflow:**
   - Work on the active branch (`dev`).
   - Use conventional commit messages (e.g. `feat(pkg): ...`, `fix(config): ...`, `feat(gnome): ...`, `feat(hyprland): ...`).

# Project Structure

The Arch Install project is organized into modular phases and core libraries to ensure a reproducible and maintainable installation process.

## Root Directory

- `arch-install`: Bash wrapper script that acts as the main entry point for both Phase 1 and Phase 2.
- `CLAUDE.md`: Context and mandates for AI agents working on this codebase.
- `Structure.md`: This file.
- `README.md`: High-level project documentation.
- `TODO`: Tracking pending features and fixes.
- `assets/`: Local binary assets (icons, cursors, wallpapers) used during configuration.
- `logs/`: Directory for execution logs and the `state.json` file for tracking progress.

## Configuration (`config/`)

- `base_{core,packages,features,config}.yaml`: Shared defaults split across core settings, package lists, enabled features, and GNOME/theme settings.
- `{profile}_{core,packages,features,config}.yaml`: Machine-specific overrides that merge on top of the corresponding base files.
- `package_profiles.yaml`: Maps high-level groups (e.g., `gnome`, `internet`) to actual package names and systemd services.
- `secrets.yaml`: (Ignored by git) Contains sensitive data like passwords and VPN credentials (can be stored encrypted as `secrets.yaml.age`).
- `dconf/`: Per-profile GNOME gsettings mappings applied during Phase 2. Files use the same inheritance model as the main config (`base_dconf.yaml`, `laptop_dconf.yaml`, etc.).

## Core Library (`core/`)

- `helper_basic.py`: Low-level shell execution (`run`, `chroot`), kernel parameter application, and user interaction.
- `helper_core.py`: Configuration loading, profile merging, and path resolution.
- `helper_disk.py`: Disk and partition identification helpers.
- `helper_gnome.py`: Shared GNOME helpers (session detection, desktop name normalisation).
- `helper_network.py`: Connectivity checks and WiFi setup for the live ISO.
- `logger.py`: Centralized logging setup.
- `resolver.py`: Dynamic resolution of package lists based on hardware (CPU/GPU) and selected profiles.
- `state.py`: Idempotency logic using `state.json` to track completed steps.
- `validator.py`: Schema validation for the YAML configuration.

## Features (`features/`)

Standalone modules for post-installation system features. Each module typically defines its own packages, services, and configuration logic.
- `ananicy.py`: Auto NICe daemon (`ananicy-cpp`) for application responsiveness.
- `antigravity.py`: Custom environment tweaks.
- `btrfs_maintenance.py`: Automated Btrfs scrub, balance, trim, and defrag scheduling.
- `claude_code.py`: Setup environment configurations for Claude Code.
- `firewall.py`: Firewalld setup.
- `local_aur_repo.py`: Pacman local repository for building and hosting custom AUR packages.
- `pia.py`: Private Internet Access VPN setup.
- `plymouth.py`: Boot splash screen configuration.
- `reflector.py`: Pacman mirrorlist optimisation.
- `snapper.py`: Btrfs snapshot management.
- `tailscale.py`: Tailscale VPN integration.
- `webapps.py`: FirefoxPWA installation and desktop launchers synchronization.
- `zram.py`: Zram-generator configuration.

## Phase 1: Pre-reboot (`prereboot/`)

Executed from the Arch Live ISO.
- `main.py`: Orchestrates the pre-install steps.
- `disk.py`: Partitioning, formatting, and mounting logic for Btrfs.
- `archinstall.py`: System configuration (hostname, locale, users, autologin, tweaks).
- `bootloader.py`: Installation and configuration of systemd-boot and rEFInd (incorporates Nvidia Early KMS setup).
- `system.py`: Package installation and service enablement via chroot.

## Scripts (`scripts/`)

Utility scripts for development and maintenance — not part of the install flow.
- `dconf_to_yaml.py`: Dumps live dconf settings into the YAML format used by `config/dconf/`.

## Phase 2: Post-reboot (`postreboot/`)

Executed after rebooting into the new system.
- `main.py`: Orchestrates the post-install steps.
- `gnome_config.py`: Detailed GNOME environment setup (gsettings, extensions, keybindings, color profiles).
- `themes.py`: Application of icons, cursors, and wallpapers.
- `dotfiles.py`: Deployment of user configuration files.
- `aur.py`: Installation of the AUR helper and requested AUR packages.
- `config_steps.py`: Miscellaneous system configuration (network optimisations, Citrix, etc.).
- `home_shortcuts.py`: Sets up standard XDG user directories and custom mount points.
- `feature_orchestrator.py`: Dynamic runner that iterates over and runs all enabled features.
- `feature_manual_install.py`: Standalone runner to install and configure a single named feature (`./arch-install feature <name>`).


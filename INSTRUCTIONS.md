# INSTRUCTIONS.md

This file provides guidance to AI assistants when working with code in this repository, alongside an overview of the project structure.

## What This Project Does

Automated Arch Linux installer and post-install configurator. Two-phase execution:

- **Phase 1** (`prereboot/`): Run from the Arch live ISO. Partitions disk (Btrfs), runs `pacstrap`, sets up locale/hostname/users, installs bootloader.
- **Phase 2** (`postreboot/`): Run after rebooting into the new system. Installs AUR packages, configures GNOME, applies themes/dotfiles, enables system features.

## Project Structure

The Arch Install project is organized into modular phases and core libraries to ensure a reproducible and maintainable installation process.

### Root Directory

- `arch-install`: Bash wrapper script that acts as the main entry point for both Phase 1 and Phase 2.
- `INSTRUCTIONS.md`: AI instructions, project structure, and key commands (this file).
- `README.md`: High-level project documentation.
- `TODO`: Tracking pending features and fixes.
- `assets/`: Local binary assets (icons, cursors, wallpapers) used during configuration.
- `logs/`: Directory for execution logs and the `state.json` file for tracking progress.

### Configuration (`config/`)

- `profiles/`: Machine profile configurations (`base.yaml` shared base, plus `{profile}.yaml` machine overrides like `desktop.yaml`, `laptop.yaml`, `server.yaml`).
- `dconf/`: GNOME gsettings mappings (`base.yaml` shared defaults, `{profile}.yaml` per-machine overrides).
- `ssh/`: SSH server authorized keys (`base.yaml`) and client keypairs (`{profile}.yaml[.age]`).
- `secrets/`: Sensitive data like passwords, VPN credentials (`secrets.yaml[.age]`), and live ISO Wi-Fi (`wifi.yaml`).
- `package_profiles.yaml`: Maps high-level package groups (e.g., `gnome`, `internet`) to package names and systemd services.

### Core Library (`core/`)

- `shell.py`: Low-level shell execution (`run`, `chroot`), kernel parameter application, and user interaction.
- `config.py`: Configuration loading, profile merging, and path resolution.
- `disk.py`: Disk and partition identification helpers.
- `gnome.py`: Shared GNOME helpers (session detection, desktop name normalisation).
- `network.py`: Connectivity checks and WiFi setup for the live ISO.
- `installer.py`: High-level pacman & AUR package installation helper.
- `logger.py`: Centralized logging setup.
- `resolver.py`: Dynamic resolution of package lists based on hardware (CPU/GPU) and selected profiles.
- `state.py`: Idempotency logic using `state.json` to track completed steps.
- `validator.py`: Schema validation for the YAML configuration.

### Features (`features/`)

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

### Phase 1: Pre-reboot (`prereboot/`)

Executed from the Arch Live ISO.
- `main.py`: Orchestrates the pre-install steps.
- `disk.py`: Partitioning, formatting, atomic resetting, and mounting logic for Btrfs.
- `archinstall.py`: System configuration (hostname, locale, users, autologin, systemd-resolved DNS, sudoers drop-in).
- `bootloader.py`: Installation and configuration of UKI bootloaders (systemd-boot, Limine, rEFInd, or direct EFI NVRAM registration) with Nvidia Early KMS setup.
- `system.py`: Package installation and service enablement via chroot.

### Scripts (`scripts/`)

Utility scripts for development and maintenance — not part of the install flow.
- `encrypt_secrets.py`: Encrypts `config/secrets/secrets.yaml` and `config/ssh/*.yaml` using `age`.
- `decrypt_secrets.py`: Decrypts `.age` files back to plaintext for editing.
- `gen-ssh-key.py`: Generates ed25519 SSH keypairs per profile and updates authorized keys.
- `dconf_to_yaml.py`: Dumps live dconf settings into the YAML format used by `config/dconf/`.

### Phase 2: Post-reboot (`postreboot/`)

Executed after rebooting into the new system.
- `main.py`: Orchestrates the post-install steps.
- `gnome.py`: Detailed GNOME environment setup (gsettings, extensions, keybindings, color profiles).
- `themes.py`: Application of icons, cursors, and wallpapers.
- `dotfiles.py`: Deployment of user configuration files.
- `aur.py`: Installation of the AUR helper (`paru`) and requested AUR packages.
- `system_config.py`: System level configuration (network hosts file, Citrix, etc.).
- `user_dirs.py`: Sets up standard XDG user directories and symlinks.
- `features.py`: Dynamic runner that iterates over and runs all enabled features.
- `feature_cli.py`: Standalone CLI runner to install and configure a single named feature (`./arch-install feature <name>`).

## Key Commands

```bash
# Phase 1 — from live ISO as root
./arch-install laptop

# Phase 2 — after reboot
./arch-install post

# Reset state to re-run steps
./arch-install clean
```

The profile name (`laptop`, `desktop`, `server`) is written as an empty marker file in the project root on first run and auto-detected on subsequent runs.

## Architecture

### Configuration System (`config/`)

Profiles inherit from `config/profiles/base.yaml`. `load_profile_config()` in `core/config.py` deep-merges them:
- **Dicts**: deep-merged (child overrides keys)
- **Lists of plain values**: concatenated
- **Lists of dicts with a `name` key** (e.g., `subvolumes`): merged by name — child entries update matching base entries

`config/secrets/secrets.yaml` (git-ignored) is automatically merged into the root config at load time. Alternatively, store secrets encrypted as `config/secrets/secrets.yaml.age` — the installer will prompt for the passphrase once at startup and decrypt it in memory. To encrypt it:

```bash
python3 scripts/encrypt_secrets.py
```

`logs/merged_config.yaml` is written after every load for debugging. Secret fields (`root_password`, `user_password`, `password`) are redacted to `***` in that file.

GNOME dconf settings live in `config/dconf/` with their own inheritance (`base.yaml`, `desktop.yaml`, etc.), resolved separately via `get_dconf_path()`.

### Package Resolution (`core/resolver.py`)

`resolve_system(config)` builds final package lists by combining:
1. `pkgprofile.core` → maps to `core_profiles` in `package_profiles.yaml`
2. `pkgprofile.post` / `pkgprofile.extras` → maps to `post_profiles`
3. `machine_specific.pacman` — direct package overrides
4. Hardware auto-detection (CPU microcode, GPU drivers) via `lscpu`/`lspci`
5. Boot profile (init system, bootloader)

Features (`features/`) are **not** resolved here — each feature module manages its own packages/services in Phase 2.

### Idempotency (`core/state.py`)

Progress is stored in `logs/state.json`. Each step calls `state.is_done(name)` before running and `state.mark_done(name)` on success. To re-run a specific step, edit `state.json` and remove the entry, or `state.reset(name)` programmatically.

### Feature Modules (`features/`)

Each feature (`firewall`, `zram`, `tailscale`, etc.) is a standalone module. Features are gated by an `enabled: true` flag in the YAML config. `postreboot/feature_orchestrator.py` iterates and dispatches them.

### GNOME Configuration

All GNOME settings live under the `gnome:` key in YAML. Sub-sections (`gsettings`, `extensions`, `keybindings`, `color_profiles`, `lockscreen_scaling`) each require `enabled: true`. Extensions are opened as Firefox tabs for manual installation — they are not installed automatically.

## Adding a New Profile

1. Create `config/<name>.yaml` with `extends: base` and override only what differs.
2. Optionally add `config/dconf/<name>.yaml` with `extends: base` for dconf overrides.
3. Run `./arch-install <name>` — the marker file is created automatically.

## Logs and Debugging

- `logs/prereboot.log`, `logs/postreboot.log` — execution logs
- `logs/state.json` — step completion state
- `logs/merged_config.yaml`, `logs/merged_dconf.yaml` — resolved config after inheritance/merge

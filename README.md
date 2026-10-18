# Arch Linux Automated Installer v0.4

A modular, profile-based Arch Linux installer and post-installation configuration tool. This project automates everything from initial disk partitioning in the live ISO to setting up a fully themed and configured GNOME desktop environment.

## Features

- **Modular Architecture**: Separate phases for pre-reboot (installation) and post-reboot (configuration).
- **Domain-Based Configuration**: Clean subdirectory hierarchy (`config/profiles/`, `config/dconf/`, `config/ssh/`, `config/secrets/`) with inheritance and deep merging.
- **Unified Kernel Image (UKI)**: 100% UKI-first architecture supporting Secure Boot, measured boot, and `/etc/kernel/install.conf` automatic triggers.
- **Bootloader Choice**: Native UKI support for `limine`, `systemd-boot`, or direct UEFI NVRAM registration (`none`).
- **Hardware-Aware**: Automatically detects CPU (Intel/AMD) and GPU (AMD/Nvidia/Intel) to install appropriate microcode, KMS drivers, and packages.
- **Btrfs-First & Atomic Resets**: Defaults to Btrfs subvolume layout with atomic subvolume reset (`delete` + `create`) on clean reinstalls.
- **Desktop Environments**: Supports automated setup of **GNOME** (dconf, extensions, dock, app grid) and **Hyprland** (Lua configuration, Quickshell top bar, Omarchy shell, Satty screenshot tools).
- **Unified Dotfiles via Chezmoi**: Central Git-backed dotfiles (`m9aj/dotfiles`) with hardware-specific templating, role targeting (`laptop`, `desktop`, `server`), headless server filtering, and native `age` encryption for credentials.
- **Antigravity AI Integration**: Bundled AI skills (`arch-install-pilot`, `hyprland-pilot`, `media-server-pilot`) and synchronization rulebooks deployed automatically into `~/.gemini/config/`.
- **Idempotency**: Progress tracked in `logs/state.json`, allowing the installer to safely resume from failure.
- **Modern System Integration**: Out-of-the-box `systemd-resolved` NetworkManager integration and `paru` AUR helper.

## Prerequisites

1.  **Arch Linux Live ISO**: Boot from the official Arch ISO.
2.  **Internet Connection**: Required for `pacstrap` and package installation.
3.  **Local Repository**: This project should be cloned or available on a mounted drive.

## Usage

### Phase 1: Installation (Pre-reboot)
Run from the live ISO environment:
```bash
cd arch_install
./arch-install laptop
```
This phase handles:
-   Disk partitioning and formatting (Btrfs subvolume layout).
-   Mounting subvolumes.
-   `pacstrap` of core system and microcode.
-   Generating `fstab`, `systemd-resolved` DNS stub, and initial system configuration.
-   Generating UKI (`/efi/EFI/Linux/arch-*.efi`) and installing bootloader (`limine`, `systemd-boot`, or `none`).

### Phase 2: Configuration (Post-reboot)
After rebooting into the new system:
```bash
cd ~/Arch/arch_install
./arch-install post
```
This phase handles:
-   Installing AUR helper (`paru`) and requested packages.
-   Enabling system features (firewall, zram, tailscale, snapper, btrfs-maintenance, antigravity).
-   Restoring persistent `age` decryption keys and applying unified `chezmoi` dotfiles.
-   Applying desktop settings:
    - **GNOME**: dconf/gsettings, custom keybindings, dock, and extensions.
    - **Hyprland**: Lua configurations, Quickshell top bar, Omarchy themes, and Satty.
-   Applying themes, cursors, and wallpapers.
-   Configuring color profiles, static network hosts, and user directories.
-   Deploying Antigravity AI skills and global workspace synchronization rules.

## Project & Configuration Structure

```
arch_install/
├── arch-install               # Master CLI entrypoint
├── assets/                    # Deployed system assets & AI pilots
│   ├── gemini/                # Antigravity rules and specialized skills
│   │   ├── GEMINI.md          # Global system modification & sync rules
│   │   └── skills/            # AI skills (arch-install-pilot, hyprland-pilot, media-server-pilot)
│   ├── hyprland/              # Hyprland lua configs, Omarchy shell, Satty config
│   ├── cursors.zip            # Custom cursor themes
│   ├── icons.zip              # System icon sets
│   └── limine-wallpaper.jpg   # Limine boot splash
│
├── config/                    # Machine & environment configuration
│   ├── profiles/              # Machine profiles (base.yaml, laptop.yaml, desktop.yaml, server.yaml)
│   ├── dconf/                 # GNOME gsettings / dconf overrides
│   ├── ssh/                   # SSH keypairs & authorized keys
│   ├── secrets/               # Passwords & bootstrap networking (secrets.yaml.age, wifi.yaml)
│   └── package_profiles.yaml  # High-level package group mapping lookup table
│
├── core/                      # Core installation engine (disk, network, resolver, validator)
├── features/                  # Standalone feature modules (antigravity, firewall, zram, tailscale, etc.)
├── prereboot/                 # Phase 1 scripts
├── postreboot/                # Phase 2 scripts (gnome, hyprland, dotfiles, aur, themes)
└── scripts/                   # Maintenance utilities (secret encryption, key generation)
```

Profiles: `laptop` (hostname: `Io`), `desktop` (hostname: `Titan`), `server` (hostname: `Media`).

Key sections in `profiles/base.yaml`:
-   `disk`, `root`, `boot`, `system`: Storage partitioning, init/bootloader, accounts.
-   `pkgprofile`, `machine_specific`: System & AUR package lists.
-   `features`: Standalone modules (tailscale, zram, firewall, btrfs_maintenance, antigravity, etc.).
-   `postconfig`: GNOME / Hyprland configuration, dotfiles, themes, user directories.

## SSH Key Authentication

SSH is configured as a feature module (`features/ssh.py`) with two roles:

- **Server**: runs `sshd`, deploys `authorized_keys`, disables password auth. Enabled on all machines.
- **Client**: deploys your private/public keypair to `~/.ssh/`. Enabled on laptop and desktop only.

| Machine | Accepts inbound SSH | Sends outbound SSH |
|---------|:-------------------:|:------------------:|
| Laptop  | yes | yes |
| Desktop | yes | yes |
| Server  | yes | no  |

The `@ssh` Btrfs subvolume persists `/etc/ssh` across reinstalls, so the server's host keys survive — connected machines won't get a "host identification changed" warning after a reinstall.

### Setup

**1. Generate keypairs** for all client-enabled profiles:
```bash
python3 scripts/gen-ssh-key.py
```
This generates an ed25519 keypair per profile, writes `config/ssh/{profile}.yaml`, and updates `config/ssh/base.yaml` with the new public keys. Pass a profile name to generate for one machine only.

**2. Encrypt the SSH key files** (see Secrets & Encryption below).

## Secrets & Encryption

Sensitive files (`config/secrets/secrets.yaml`, `config/ssh/*.yaml`) can be encrypted with [age](https://age-encryption.org/) before storing. `wifi.yaml` is intentionally left unencrypted — it is read before age is available during the live ISO phase.

### Encrypting

```bash
python3 scripts/encrypt_secrets.py
```

Prompts for a passphrase once, encrypts `config/secrets/secrets.yaml` and `config/ssh/*.yaml` to `.age` files, then offers to delete the plaintext originals.

### Running with encrypted secrets

The installer prompts for your passphrase once at startup and decrypts all `.age` files in memory — the passphrase is not stored on disk. `wifi.yaml` is intentionally left unencrypted so the network can connect before age is available.

### Re-editing encrypted files

```bash
python3 scripts/decrypt_secrets.py
# edit the plaintext files, then re-encrypt
python3 scripts/encrypt_secrets.py
```

## Unified Dotfiles & Chezmoi

Dotfiles are managed via a centralized, Git-backed repository ([`m9aj/dotfiles`](https://github.com/m9aj/dotfiles.git)) using [chezmoi](https://www.chezmoi.io/) across Laptop (`Io`), Desktop (`Titan`), and Media Server (`Media`).

### Features & Security
- **Role Detection (`.chezmoi.toml.tmpl`)**: Derives `role` (`laptop`, `desktop`, `server`) and `is_gui` (`true`/`false`) dynamically from the machine hostname.
- **Headless Filtering (`.chezmoiignore`)**: On headless servers (`is_gui == false`), all GUI applications (VS Code, GTK bookmarks, Citrix, PWAs, icons, `monitors.xml`) are omitted.
- **Hardware Display Profiles (`dot_config/monitors.xml.tmpl`)**: Renders display configurations matching each physical machine (Framework 2.8K display vs Samsung 4K HDR display).
- **Encrypted Secrets (`age`)**: Credentials (`~/.git-credentials`) and SSH server definitions (`~/.ssh/config`) are encrypted at rest with `age`.
- **Installer Integration (`postreboot/dotfiles.py`)**: Automatically restores the decryption key from persistent storage (`/home/ajay/Arch/config/chezmoi-key.txt`), initializes chezmoi, and applies dotfiles non-interactively.

## Antigravity AI Customizations & Pilots

The installer includes specialized AI runbooks, skills, and synchronization rules in `assets/gemini/`:

- **Master Rulebook (`assets/gemini/GEMINI.md`)**: Enforces the system modification and synchronization policy. Whenever system packages, network hosts, GNOME/Hyprland configs, or services are changed outside the repo, Antigravity prompts to persist those changes into `arch_install`.
- **Automated Deployment (`features/antigravity.py`)**: Installs the Antigravity CLI and automatically symlinks all skills and the global rulebook to `~/.gemini/config/`.
- **Specialized Pilots (`assets/gemini/skills/`)**:
  - `arch-install-pilot`: Full subsystem mapping and instructions for updating installer profiles, features, and assets.
  - `hyprland-pilot`: Hyprland Lua settings, window rules, scratchpads, Quickshell top bar, and Omarchy shell management.
  - `media-server-pilot`: Remote container and service management on `media.local` via SSH.

## Maintenance

-   **Logs**: Check `logs/` for detailed execution logs and `state.json` for progress tracking.
-   **Debug**: `logs/merged_config.yaml` shows the fully merged config after each run (secrets redacted).

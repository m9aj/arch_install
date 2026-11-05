# Arch Linux Automated Installer & System Configurator

A modular, profile-based Arch Linux installer and post-installation configuration engine. This project automates the entire lifecycle—from disk partitioning, subvolume creation, and UKI generation on the live ISO, to setting up dotfiles, persistent package caches, and customized desktop environments (GNOME & Hyprland) post-reboot.

---

## Key Highlights

- **Modular Two-Phase Execution**:
  - **Phase 1 (`prereboot/`)**: Partitioning, subvolumes, `pacstrap`, system configuration, and UKI generation run from the official Arch live ISO.
  - **Phase 2 (`postreboot/`)**: Non-root configuration after first reboot: AUR package builds, dotfiles, system features, themes, and desktop environments.
- **Domain-Based Configuration**: Clean inheritance (`config/profiles/base.yaml` + machine overrides: `laptop.yaml`, `desktop.yaml`, `server.yaml`).
- **Unified Kernel Image (UKI) First**: 100% UKI architecture supporting direct UEFI NVRAM boot, Limine, or systemd-boot with early Nvidia KMS.
- **Persistent AUR Cache**: Btrfs `@pkg` subvolume (`/var/cache/pacman/pkg`) shared with `paru`/`makepkg`, allowing instant reinstalls without recompilation.
- **Desktop Environments**: Full automated configuration for **GNOME** (dconf, extensions, keybindings, app grid) and **Hyprland** (Lua configs, Quickshell top bar, Impasto patcher).
- **Dotfiles with Chezmoi & Age**: Centrally managed dotfiles (`m9aj/dotfiles`) with hardware display matching, role targeting, and persistent `age` key decryption.
- **Antigravity AI Integration**: Bundled AI agent skills (`arch-install-pilot`, `hyprland-pilot`, `media-server-pilot`) and synchronization rules automatically deployed to `~/.gemini/config/`.
- **Idempotent State Engine**: Execution progress tracked in `logs/state.yaml` with atomic saves, step resets, and status inspection.

---

## Quick Start

### 1. Prerequisites
1. **Arch Linux Live ISO**: Boot from the official Arch ISO.
2. **Internet Connection**: Active Ethernet or Wi-Fi.
3. **Installer Repository**: Clone the repository or download via script:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/m9aj/arch_install/main/scripts/github_download.sh | bash
   cd arch_install
   ```

### 2. Verify & Dry-Run Test
Before touching disks, validate your machine configuration and run health checks:
```bash
./arch-install check laptop     # Dry-run validate profile config & partitions
./arch-install test             # Run automated health and sanity checks
./arch-install status           # Inspect current state of steps and features
```

### 3. Phase 1: Installation (Pre-Reboot)
Run as root from the Arch live ISO:
```bash
./arch-install laptop           # or desktop / server
```
*Handles: Btrfs subvolumes, mount ordering, pacstrap, fstab, hostname, timezone, locale, users, secure passwords, kernel cmdline, and UKI bootloader.*

### 4. Phase 2: Configuration (Post-Reboot)
Reboot into the newly installed system, open a terminal as your regular user, and run:
```bash
cd ~/Projects/arch_install
./arch-install post
```
*Handles: User directories, chezmoi dotfiles, static hosts, AUR helper (`paru`), features (firewall, zram, tailscale, snapper, btrfs maintenance), desktop environments (GNOME / Hyprland), and Antigravity AI skills.*

---

## CLI Command Reference

The master CLI entrypoint [`./arch-install`](arch-install) provides all management commands:

| Command | Description |
| :--- | :--- |
| `./arch-install [profile]` | Run **Phase 1** (pre-reboot) from live ISO as root. Profile is saved as an active marker file. |
| `./arch-install post [profile]` | Run **Phase 2** (post-reboot) as regular user. Automatically uses the active profile marker. |
| `./arch-install status` | Display a color-coded table of all Phase 1 steps, Phase 2 steps, and features with timestamps. |
| `./arch-install check [profile]` | Dry-run validate profile YAML syntax, required fields, and partition paths without making changes. |
| `./arch-install test` | Run project test suite: Python syntax compilation, feature imports, package profiles, and profile schemas. |
| `./arch-install list` | List all available system features and package groups with status and package details. |
| `./arch-install list features` | List only standalone features in `features/*.py` with configured status. |
| `./arch-install list packages` | List package groups from `config/package_profiles.yaml`. |
| `./arch-install feature <name> [profile]` | Manually install and configure a single named feature (e.g. `./arch-install feature tailscale`). |
| `./arch-install pkg <group> [group2 ...]` | Install package group(s) from `package_profiles.yaml` (e.g. `./arch-install pkg internet creative`). |
| `./arch-install reset <step>` | Mark a completed step as pending so it re-runs on next invocation. |
| `./arch-install reset all` | Mark all steps as pending while preserving logs and state history. |
| `./arch-install clean` | Remove active profile markers, pycache directories, and empty `logs/`. |

---

## Project Structure

```
arch_install/
├── arch-install               # Master CLI entrypoint
├── README.md                  # Comprehensive documentation and developer guide
├── .gitignore                 # Secrets, runtime logs, and profile marker exclusions
│
├── config/                    # Machine & environment configuration
│   ├── profiles/              # Machine profiles (base.yaml, laptop.yaml, desktop.yaml, server.yaml)
│   ├── dconf/                 # GNOME gsettings / dconf overrides (base.yaml, desktop.yaml, etc.)
│   ├── ssh/                   # SSH keypairs & authorized keys (base.yaml, desktop.yaml.age, etc.)
│   ├── secrets/               # Passwords & Wi-Fi bootstrap (secrets.yaml.age, wifi.yaml.template)
│   └── package_profiles.yaml  # High-level package group lookup table
│
├── core/                      # Core engine
│   ├── shell.py               # Process execution (run, chroot, input_data piping, confirm)
│   ├── kernel.py              # Unified cmdline management and UKI regeneration
│   ├── config.py              # Profile loader, deep merge, and path resolution
│   ├── disk.py                # Disk and partition resolution helpers (get_partition, get_root_partition)
│   ├── desktop.py             # Desktop environment detection (GNOME / Hyprland / KDE)
│   ├── network.py             # Connectivity verification & live ISO Wi-Fi setup
│   ├── installer.py           # High-level pacman & AUR package installation helper
│   ├── resolver.py            # Hardware detection (CPU microcode, GPU drivers) & package resolver
│   ├── validator.py           # Schema validator for configuration YAMLs
│   ├── state.py               # Atomic state engine (logs/state.yaml)
│   └── logger.py              # Centralized logging setup
│
├── prereboot/                 # Phase 1 scripts (run from live ISO)
│   ├── main.py                # Pre-reboot step orchestrator
│   ├── disk.py                # Btrfs formatting, subvolume creation, and mount ordering
│   ├── archinstall.py         # pacstrap, fstab, locale, timezone, user, secure passwords, tweaks
│   ├── system.py              # Post-base package installation and service enablement via chroot
│   └── bootloader.py          # UKI generation and bootloader installation (Limine, systemd-boot, none)
│
├── postreboot/                # Phase 2 scripts (run after first reboot)
│   ├── main.py                # Post-reboot step orchestrator (dependency-ordered)
│   ├── aur.py                 # AUR helper bootstrap (paru) & cache-first package installer
│   ├── features.py            # Dynamic runner for enabled standalone features
│   ├── gnome.py               # GNOME setup (dconf, extensions, keybindings, app grid, dock)
│   ├── hyprland.py            # Hyprland setup via Impasto unattended patcher
│   ├── dotfiles.py            # Chezmoi dotfiles deployment with age key recovery
│   ├── user_dirs.py           # XDG user directories & symlinks to persistent storage
│   ├── system_config.py       # Static /etc/hosts entries and Citrix ICA client configuration
│   ├── themes.py              # Cursor themes and wallpaper installers
│   ├── status_cli.py          # ./arch-install status engine
│   ├── list_cli.py            # ./arch-install list engine
│   ├── feature_cli.py         # ./arch-install feature runner
│   └── pkg_cli.py             # ./arch-install pkg runner
│
├── features/                  # Standalone feature modules
│   ├── ananicy.py             # Application responsiveness daemon (ananicy-cpp)
│   ├── antigravity.py         # Antigravity CLI & AI pilot skills deployment
│   ├── btrfs_maintenance.py   # Scheduled Btrfs scrub, balance, trim, and defrag
│   ├── firewall.py            # Firewalld daemon & zones
│   ├── pia.py                 # Private Internet Access VPN with NetworkManager keyfiles
│   ├── plymouth.py            # Boot splash screen & reliable mkinitcpio hook injection
│   ├── reflector.py           # Mirrorlist ranking & timer
│   ├── snapper.py             # Snapper timeline snapshots on Btrfs subvolumes
│   ├── ssh.py                 # OpenSSH server hardening & client key deployment
│   ├── tailscale.py           # Tailscale mesh VPN with non-root operator setup
│   ├── webapps.py             # FirefoxPWA integration & desktop launcher synchronization
│   └── zram.py                # zram-generator swap & live kernel VM tuning
│
├── assets/                    # Assets and AI skills
│   ├── gemini/                # Antigravity master rule (GEMINI.md) & AI skills
│   ├── hyprland/              # Impasto overrides, settings.json, patch-impasto.py
│   ├── cursors.zip            # Cursor theme archives
│   └── limine-wallpaper.jpg   # Limine boot splash
│
├── scripts/                   # Verification and maintenance utilities
│   ├── test_project.py        # Project test suite & dry-run validator (./arch-install test / check)
│   ├── encrypt_secrets.py     # Age encryption utility for secrets and SSH keys
│   ├── decrypt_secrets.py     # Age decryption utility for plaintext editing
│   ├── gen-ssh-key.py         # Ed25519 SSH keypair generator
│   └── github_download.sh     # Bootstrapping download script for live ISO
│
└── logs/                      # Runtime logs and state (git-ignored)
    ├── prereboot.log          # Phase 1 execution log
    ├── postreboot.log         # Phase 2 execution log
    ├── state.yaml             # Step completion state
    └── merged_config.yaml     # Debug dump of resolved config (passwords redacted)
```

---

## Configuration & Profiles

### Profile Inheritance & Deep Merging
Machine configurations in `config/profiles/` inherit from `base.yaml`. When [`core.config.load_profile_config()`](core/config.py) runs:
1. **Dictionaries**: Deep-merged (child machine overrides keys, preserves unspecified base keys).
2. **Lists of plain values**: Concatenated without duplicates.
3. **Lists of dictionaries with a `name` key** (such as `subvolumes`): Merged by `name`—child profile entries update the matching base subvolume entry.

### Available Profiles
- **`laptop`** (Hostname: `Io`): Framework laptop, Wi-Fi bootstrap, power management, display scaling.
- **`desktop`** (Hostname: `Titan`): Workstation, Nvidia/AMD GPU drivers, multi-monitor configuration, secondary drive mounts.
- **`server`** (Hostname: `Media`): Headless server, direct NVRAM boot, container hosting, minimal services.

### Adding a New Profile
1. Create `config/profiles/<machine>.yaml` with `extends: base` and override only differing keys:
   ```yaml
   extends: base
   system:
     hostname: MyMachine
   disk:
     disk_by_id: nvme-Samsung_SSD_980_PRO_2TB_...
     boot_part: -part1
     root_part: -part2
   ```
2. Optionally create `config/dconf/<machine>.yaml` for GNOME desktop overrides.
3. Test with `./arch-install check <machine>`.

---

## Package Architecture & Persistent Cache

### Package Resolution (`core/resolver.py`)
Package lists are constructed dynamically using `config/package_profiles.yaml`:
1. **Core Packages**: `pkgprofile.core` maps to `core_profiles` (base system, kernel, file systems, networking).
2. **Post Packages**: `pkgprofile.post` and `pkgprofile.extras` map to `post_profiles` (desktop, audio, fonts, tools).
3. **Hardware Drivers**: Automatically detects CPU vendor (`intel-ucode` / `amd-ucode`) and GPU hardware (`mesa`, `vulkan-radeon`, `nvidia-open`, etc.).

### Persistent AUR Cache in `@pkg` Subvolume
AUR packages and the AUR helper (`paru`) are built with `PKGDEST="/var/cache/pacman/pkg"` in `/etc/makepkg.conf`.
- `/var/cache/pacman/pkg` is mapped to its own persistent Btrfs subvolume (`@pkg`).
- When reinstalls occur, `@pkg` is **reused** rather than reformatted.
- [`postreboot/aur.py`](postreboot/aur.py) checks the cache first: if `package-version.pkg.tar.zst` exists, it installs instantly with `pacman -U`, bypassing AUR compilation.

---

## Security, Secrets & SSH

### Age Encryption
Sensitive configuration files are encrypted using [age](https://age-encryption.org/) in passphrase mode:
- `config/secrets/secrets.yaml.age`: Passwords, VPN credentials.
- `config/ssh/{profile}.yaml.age`: Machine-specific private keys.
- **Plaintext files are git-ignored**. Templates are provided:
  - `config/secrets/secrets.yaml.template`
  - `config/secrets/wifi.yaml.template`
- Encrypt and decrypt using helper scripts:
  ```bash
  python3 scripts/encrypt_secrets.py
  python3 scripts/decrypt_secrets.py
  ```
- During Phase 1 and Phase 2, the installer prompts for the Age passphrase once and decrypts into memory.

### SSH Key Deployment
Configured via `features/ssh.py` with two distinct roles:
- **Server Role**: Runs `sshd`, deploys `authorized_keys` from `config/ssh/base.yaml`, disables password authentication. Enabled on all machines.
- **Client Role**: Deploys private/public keypair to `~/.ssh/id_ed25519`. Enabled on desktop and laptop.
- Generate new keypairs with:
  ```bash
  python3 scripts/gen-ssh-key.py [profile]
  ```

---

## Dotfiles & Chezmoi

User dotfiles are managed via [chezmoi](https://www.chezmoi.io/) backed by `m9aj/dotfiles`:
- **Persistent Key Recovery**: Restores `chezmoi-key.txt` automatically from persistent storage into `~/.config/chezmoi/key.txt`.
- **Dynamic Device Roles**: Evaluates `.chezmoi.toml.tmpl` to target machine role (`laptop`, `desktop`, `server`) and GUI availability (`is_gui`).
- **Display Configurations**: Renders `monitors.xml` customized per physical display.
- **Headless Filtering**: `.chezmoiignore` automatically omits GUI applications and desktop settings on servers.

---

## Antigravity AI Customizations & Synchronization Policy

AI agent customizations are centralized in `assets/gemini/` and automatically deployed post-reboot:
- **Workspace Synchronization Rule (`GEMINI.md`)**:
  > *Whenever an agent makes modifications to the running machine outside the `arch_install` repository (packages, `/etc/` configs, desktop settings, dotfiles, network hosts), it MUST prompt the user with the option to persist those changes into `arch_install`.*
- **Automated Deployment (`features/antigravity.py`)**: Automatically links pilot skills and rules into `~/.gemini/config/` and `~/.gemini/antigravity-cli/skills/`.
- **Pilot Skills**:
  - `arch-install-pilot`: Subsystem mappings and synchronization rules for installer updates.
  - `hyprland-pilot`: Hyprland window rules, Lua settings, and Quickshell top bar.
  - `media-server-pilot`: Container and Podman Quadlet management for the home media server.

---

## Developer & Architectural Guidelines

When maintaining or extending code in this repository, follow these core principles:

1. **Non-Interactive Execution**:
   - Phase 1 and Phase 2 scripts must run completely non-interactively without blocking on stdin (except when explicitly asking for confirmation in format mode or the initial Age passphrase prompt).
   - Use `pacman --noconfirm`, `makepkg --noconfirm`, and direct file writes.
2. **UKI Bootloader Integrity**:
   - All boot configurations must generate a Unified Kernel Image (`/efi/EFI/Linux/arch-<kernel>.efi`).
   - Use [`core.kernel.rebuild_uki(config)`](core/kernel.py) and [`core.kernel.apply_kernel_parameter()`](core/kernel.py) as the single source of truth for kernel command lines and UKI regeneration.
3. **Phase Separation & Privileges**:
   - **Phase 1** runs as root targeting `/mnt`. System mutations use `chroot()` or direct writes to `/mnt/...`.
   - **Phase 2** runs as the normal desktop user. System operations use `run("sudo ...")` with passwordless sudo configured in Phase 1 (`/etc/sudoers.d/10-wheel`). Never invoke `sudo` when writing to user home directories.
4. **Secure Password & Command Handling**:
   - Never interpolate passwords or secrets into shell strings or `echo` commands.
   - Use `run(..., input_data=payload, log_cmd=False)` to pipe credentials directly to process stdin without leaking to `ps aux` or command logs.
5. **Idempotency & State Tracking**:
   - Every major step must check `core.state.is_done(name)` and call `core.state.mark_done(name)` upon completion.
   - The state engine writes atomically to `logs/state.yaml` with backup `.bak` files.
6. **Btrfs Subvolume Mount Ordering**:
   - When mounting subvolumes, always sort by mount point path length/depth (shortest first) so root `/mnt/` is mounted before nested child mounts (`/home`, `/var/log`).

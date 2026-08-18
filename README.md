# Arch Linux Automated Installer v0.4

A modular, profile-based Arch Linux installer and post-installation configuration tool. This project automates everything from initial disk partitioning in the live ISO to setting up a fully themed and configured GNOME desktop environment.

## Features

## Features

- **Modular Architecture**: Separate phases for pre-reboot (installation) and post-reboot (configuration).
- **Domain-Based Configuration**: Clean subdirectory hierarchy (`config/profiles/`, `config/dconf/`, `config/ssh/`, `config/secrets/`) with inheritance and deep merging.
- **Unified Kernel Image (UKI)**: 100% UKI-first architecture supporting Secure Boot, measured boot, and `/etc/kernel/install.conf` automatic triggers.
- **Bootloader Choice**: Native UKI support for `limine`, `systemd-boot`, or direct UEFI NVRAM registration (`none`).
- **Hardware-Aware**: Automatically detects CPU (Intel/AMD) and GPU (AMD/Nvidia) to install appropriate microcode, KMS drivers, and packages.
- **Btrfs-First & Atomic Resets**: Defaults to Btrfs subvolume layout with atomic subvolume reset (`delete` + `create`) on clean reinstalls.
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
-   Enabling system features (firewall, zram, tailscale, snapper, btrfs-maintenance).
-   Applying GNOME settings (dconf/gsettings, custom keybindings, dock).
-   Headless/CLI installation of GNOME shell extensions.
-   Applying themes, cursors, and wallpapers.
-   Configuring color profiles and user directories.

## Configuration Structure

Configuration is organized cleanly by domain in `config/`:

```
config/
  profiles/                # Machine profiles
    base.yaml              # Shared base defaults (disk, system, boot, packages, features)
    {profile}.yaml         # Machine profile overrides (laptop.yaml, desktop.yaml, server.yaml)

  dconf/                   # GNOME gsettings / dconf overrides
    base.yaml              # Shared GNOME defaults
    {profile}.yaml         # Machine GNOME overrides

  ssh/                     # SSH keypairs & authorized keys
    base.yaml              # Shared authorized_keys for all servers (committed)
    {profile}.yaml[.age]   # Machine SSH client keypair (git-ignored, age-encrypted)

  secrets/                 # Passwords & bootstrap networking
    secrets.yaml[.age]     # System passwords & VPN credentials (git-ignored, age-encrypted)
    wifi.yaml              # Live ISO Wi-Fi credentials (git-ignored, plain text)

  package_profiles.yaml    # Global package group mapping lookup table
```

Profiles: `laptop` (hostname: Io), `desktop` (hostname: Titan), `server` (hostname: Media).

Key sections in `profiles/base.yaml`:
-   `disk`, `root`, `boot`, `system`: Storage partitioning, init/bootloader, accounts.
-   `pkgprofile`, `machine_specific`: System & AUR package lists.
-   `features`: Standalone modules (tailscale, zram, firewall, btrfs_maintenance, etc.).
-   `postconfig`: GNOME configuration, dotfiles, themes, user directories.

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

## Maintenance

-   **Logs**: Check `logs/` for detailed execution logs and `state.json` for progress tracking.
-   **Debug**: `logs/merged_config.yaml` shows the fully merged config after each run (secrets redacted).

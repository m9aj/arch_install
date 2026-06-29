# Arch Linux Automated Installer v0.4

A modular, profile-based Arch Linux installer and post-installation configuration tool. This project automates everything from initial disk partitioning in the live ISO to setting up a fully themed and configured GNOME desktop environment.

## Features

- **Modular Architecture**: Separate phases for pre-reboot (installation) and post-reboot (configuration).
- **Profile Inheritance**: Configuration files (YAML) support deep-merging of focused split files for shared defaults and machine-specific overrides.
- **Hardware-Aware**: Automatically detects CPU (Intel/AMD) and GPU (AMD/Nvidia) to install appropriate microcode and drivers.
- **Btrfs-First**: Defaults to Btrfs with optimized mount options and subvolume layouts.
- **Idempotency**: Progress is tracked in `state.json`, allowing the installer to resume from where it left off in case of failure.
- **Rich Post-Install**: Automated setup of GNOME gsettings, extensions (via Firefox-based interaction), themes, dotfiles, and system features (VPN, firewall, zram).

## Prerequisites

1.  **Arch Linux Live ISO**: Boot from the official Arch ISO.
2.  **Internet Connection**: Required for `pacstrap` and package installation.
3.  **Local Repository**: This project should be cloned or available on a mounted drive (e.g., `/mnt/Personal/_Ajay/Arch/arch_install`).

## Usage

### Phase 1: Installation (Pre-reboot)
Run from the live ISO environment:
```bash
cd arch_install
./arch-install laptop
```
This phase handles:
-   Disk partitioning and formatting (Btrfs).
-   Mounting subvolumes.
-   `pacstrap` of core system.
-   Generating `fstab` and initial system configuration.
-   Installing the bootloader (`systemd-boot`).

### Phase 2: Configuration (Post-reboot)
After rebooting into the new system:
```bash
cd ~/Arch/arch_install
sudo ./arch-install post
```
This phase handles:
-   Installing AUR helper and requested packages.
-   Enabling system features (firewall, zram, tailscale).
-   Applying GNOME settings (dconf/gsettings, custom keybindings, dock).
-   Opening Firefox tabs for manual extension installation.
-   Applying themes, cursors, and wallpapers.
-   Configuring color profiles.

## Configuration Structure

Each machine profile is split across focused files that are deep-merged in order. No `extends:` key — the loader always starts from the base splits and merges profile overrides on top.

```
config/
  base_core.yaml           # shared disk layout, system defaults, boot
  base_packages.yaml       # shared package profiles
  base_features.yaml       # all features defined, disabled by default
  base_config.yaml         # shared post-install config (GNOME, dotfiles, themes)
  base_dconf.yaml          # shared GNOME gsettings
  base_ssh.yaml            # authorized_keys for all machines (committed, no private keys)

  {profile}_core.yaml      # disk device, hostname, boot overrides
  {profile}_packages.yaml  # pkgprofile, machine_specific packages
  {profile}_features.yaml  # feature enable/disable overrides
  {profile}_config.yaml    # postconfig overrides (GNOME, dotfiles, themes)
  {profile}_dconf.yaml     # GNOME gsettings overrides

  {profile}_ssh.yaml[.age] # SSH client keypair (git-ignored, age-encrypted)
  wifi.yaml                # WiFi credentials (git-ignored, not encrypted)
  secrets.yaml[.age]       # passwords, VPN, keybindings (git-ignored, age-encrypted)
```

Profiles: `laptop` (hostname: Io), `desktop` (hostname: Titan), `server` (hostname: Media).

Key sections in `base_core.yaml`:
-   `system`: User account details, timezone.
-   `disk`: Partitioning mode and Btrfs subvolumes.

Key sections in `base_features.yaml`:
-   `features`: Standalone system modules (e.g., `tailscale`, `firewall`, `ssh`).

Key sections in `base_config.yaml`:
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
This generates an ed25519 keypair per profile, writes `config/{profile}_ssh.yaml`, and updates `config/base_ssh.yaml` with the new public keys. Pass a profile name to generate for one machine only.

**2. Encrypt the SSH key files** (see Secrets & Encryption below).

## Secrets & Encryption

Sensitive files (`secrets.yaml`, `laptop_ssh.yaml`, `desktop_ssh.yaml`) can be encrypted with [age](https://age-encryption.org/) before storing. `wifi.yaml` is intentionally left unencrypted — it is read before age is available during the live ISO phase.

### Encrypting

```bash
python3 scripts/encrypt_secrets.py
```

Prompts for a passphrase once, encrypts `secrets.yaml`, `laptop_ssh.yaml`, and `desktop_ssh.yaml` to `.age` files, then offers to delete the plaintext originals.

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

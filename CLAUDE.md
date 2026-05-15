# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Automated Arch Linux installer and post-install configurator. Two-phase execution:

- **Phase 1** (`prereboot/`): Run from the Arch live ISO. Partitions disk (Btrfs), runs `pacstrap`, sets up locale/hostname/users, installs bootloader.
- **Phase 2** (`postreboot/`): Run after rebooting into the new system. Installs AUR packages, configures GNOME, applies themes/dotfiles, enables system features.

## Key Commands

```bash
# Phase 1 — from live ISO as root
./arch-install laptop

# Phase 2 — after reboot
sudo ./arch-install post

# Reset state to re-run steps
./arch-install clean
```

The profile name (`laptop`, `desktop`, `server`) is written as an empty marker file in the project root on first run and auto-detected on subsequent runs.

## Architecture

### Configuration System (`config/`)

Profiles use `extends: base` for inheritance. `load_config()` in `core/helper_core.py` deep-merges them:
- **Dicts**: deep-merged (child overrides keys)
- **Lists of plain values**: concatenated
- **Lists of dicts with a `name` key** (e.g., `subvolumes`): merged by name — child entries update matching base entries

`secrets.yaml` (git-ignored) is automatically merged into the root config at load time. Alternatively, store secrets encrypted as `secrets.yaml.age` — the installer will prompt for the passphrase once at startup and decrypt it in memory. To create it:

```bash
age --passphrase -o config/secrets.yaml.age config/secrets.yaml
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

Each feature (`firewall`, `zram`, `tailscale`, etc.) is a standalone module. Features are gated by an `enabled: true` flag in the YAML config. `postreboot/features.py` iterates and dispatches them.

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

# Impasto Personal Overrides & Installer/Patcher

This directory holds all personal customizations on top of upstream [Impasto](https://github.com/andreumassanet/impasto). Running [`patch-impasto.py`](patch-impasto.py) downloads the latest Impasto repository, patches its package lists and configs, and launches `./setup`.

## Quick Start

### 1. Full Interactive Install (Download → Patch → `./setup` Menu)
```bash
/home/ajay/Projects/hyprland/patch-impasto.py
```
1. Clones `https://github.com/andreumassanet/impasto.git` to `/home/ajay/Projects/hyprland/impasto` (or resets it to the latest `origin/main` if already cloned).
2. Disables unwanted packages in `packages/pacman.txt` and `packages/aur.txt`.
3. Applies all Hyprland (`user-overrides.lua`) and Quickshell patches directly into `/home/ajay/Projects/hyprland/impasto/home/.config`.
4. Launches `./setup` from `/home/ajay/Projects/hyprland/impasto`.
5. Verifies that `~/.config/hypr` and `~/.config/quickshell` have all patches applied after `./setup` finishes.

### 2. Unattended Install (for automated provisioning / `arch_install`)
```bash
/home/ajay/Projects/hyprland/patch-impasto.py --unattended
```
Runs the full download → patch workflow and invokes `./setup install --skip-system --aur-helper paru --noconfirm`.

### 3. Download & Patch Only (No `./setup`)
```bash
/home/ajay/Projects/hyprland/patch-impasto.py --patch-only
```

### 4. Dry-Run Status Check
```bash
/home/ajay/Projects/hyprland/patch-impasto.py --check
```

### 5. Save Live UI Settings to Persistent Storage
```bash
/home/ajay/Projects/hyprland/patch-impasto.py --save-settings
```
Copies `~/.local/state/quickshell/settings.json` (island layout, bar icons, border size, gaps, rounding, blur, dock, and display scale) into `/home/ajay/Projects/hyprland/settings.json`, which is automatically restored whenever `patch-impasto.py` runs.

---

## What Gets Patched

1. **Disabled Packages (`packages/pacman.txt` & `packages/aur.txt`):**
   - **`pacman.txt` (14):** `fnm`, `yazi`, `imv`, `mpv`, `asciiquarium`, `neovim`, `tree-sitter-cli`, `lua-language-server`, `pyright`, `ruff`, `bash-language-server`, `sddm`, `v4l-utils`, `qemu-desktop`
   - **`aur.txt` (12):** `mpvpaper`, `wl-screenrec`, `unimatrix-git`, `cbonsai`, `tty-clock`, `lavat`, `vscodium-bin`, `zen-browser-bin`, `vesktop-bin`, `spotify`, `spicetify-cli`, `quickemu`
2. **Hyprland (`user-overrides.lua` + `hyprland.lua`):**
   - Copies [`user-overrides.lua`](user-overrides.lua) to `~/.config/hypr/user-overrides.lua` and adds `require("user-overrides")` to `hyprland.lua` (keeping all upstream files in `~/.config/hypr/modules/` untouched).
3. **Quickshell (`~/.config/quickshell`):**
   - **Launcher animations (`LauncherPanel.qml`):** Smooth sliding selection highlight and `add`/`remove`/`move`/`displaced` list transitions.
   - **3-Way Power Profile (`system.py` & `ControlsService.qml`):** Cycles `power-saver` → `balanced` → `performance`.
   - **AC / Battery Auto-Switching (`BatteryService.qml`):** Switches to `power-saver` and turns off keyboard backlight on battery; restores `balanced` on AC.
   - **GTK / Nautilus reload, LibreOffice Notebookbar styling, and Adwaita-Colors 3D Folder Icons (`theme_manager.py`).**
   - **Notification Click-to-Focus (`HyprlandService.qml`, `NotificationService.qml`, `NotificationLayer.qml`, `NotificationList.qml`):** Clicking any live toast or history notification focuses the corresponding application window (including `kitty` running `agy` for Antigravity CLI notifications).

---
name: hyprland-pilot
description: >
  Manage and customize the Hyprland desktop environment, Quickshell top bar,
  window rules, scratchpad workspaces, keybindings, cursor settings, menus,
  and dotfiles sync on Arch Linux. Triggers: Hyprland, hyprland.lua, Quickshell,
  top bar, shell.toml, status bar, launch utility, scratchpad, special workspace,
  keybindings, cursor speed, cursor theme, omarchy-menu, and dotfiles.
---

# Hyprland & Quickshell Desktop Pilot Skill

This skill guides the AI assistant when managing, tuning, or troubleshooting the user's
custom Hyprland 0.56+ and Quickshell desktop environment on Arch Linux.

---

## 1. System Architecture & Key Locations

| Component | Live Path | Repo Asset Path | Purpose |
| :--- | :--- | :--- | :--- |
| **Hyprland Config** | `~/.config/hypr/hyprland.lua` | `assets/hyprland/hypr/hyprland.lua` | Core compositor rules, binds, inputs, animations |
| **Top Bar Config** | `~/.config/omarchy/shell.toml` | `assets/hyprland/omarchy/shell.toml` | Top bar settings, independent `[bar] font-size` |
| **Shell UI QML** | `~/.local/share/omarchy/shell/` | `assets/hyprland/omarchy/shell/` | Quickshell UI components (`Commons/Style.qml`, etc.) |
| **Launcher Menu** | `~/.local/share/omarchy/default/omarchy/omarchy-menu.jsonc` | `assets/hyprland/omarchy/default/omarchy/omarchy-menu.jsonc` | Desktop launcher menu items and routes |
| **Branding / Screensaver** | `~/.config/omarchy/branding/screensaver.txt` | `assets/hyprland/omarchy/logo.txt` | Screensaver ASCII art (`ARCH`) with `ttfx` |
| **Launch Helpers** | `~/.local/bin/launch`, `~/.local/bin/xdg-open` | `assets/hyprland/omarchy/bin/` | Scratchpad decoupling & link openers |
| **Dotfiles Git Repo** | `~/Arch/arch_install` (branch `dev`) | — | Central Git repo for all system configs |

---

## 2. Hyprland 0.56+ Lua API & Dispatch Rules

Hyprland uses a pure Lua configuration with the `hl.*` API.

### Important Syntax Rules:
1. **Lua Keybinds:** Use `hl.bind("MOD + KEY", <dispatcher>, { description = "..." })`.
2. **Lua Dispatchers:** Use `hl.dsp.*` namespace:
   - Command execution: `hl.dsp.exec_cmd("command args")`
   - Close window: `hl.dsp.window.close()`
   - Toggle fullscreen: `hl.dsp.window.fullscreen()`
   - Toggle float: `hl.dsp.window.float({ action = "toggle" })`
   - Toggle scratchpad: `hl.dsp.workspace.toggle_special("workspace_name")`
   - Focus directions: `hl.dsp.focus({ direction = "left" })`
3. **CLI Dispatch Syntax:** In Hyprland 0.56+, `hyprctl dispatch <arg>` literally evaluates `hl.dispatch(<arg>)` in Lua.
   - **Correct:** `hyprctl dispatch "hl.dsp.workspace.toggle_special('antigravity')"`
   - **Incorrect:** `hyprctl dispatch togglespecialworkspace antigravity` (syntax error)
4. **Workspace Rules in Exec:** When dispatching commands with target workspace brackets, wrap with Lua raw string delimiters:
   ```bash
   hyprctl dispatch "hl.dsp.exec_cmd([=[[workspace 1] gnome-text-editor /path/to/file]=])"
   ```

---

## 3. Scratchpad & Application Decoupling

The desktop uses floating scratchpads on special workspaces:
* **Antigravity AI CLI:** Workspace `special:antigravity` (toggled with `SUPER + A`)
* **Activity Monitor (btop):** Workspace `special:btop` (toggled with `SUPER + CTRL + T`)

### Critical Decoupling Rules:
* **Never launch desktop apps directly into special workspaces:**
  If a graphical app (editor, browser, viewer) is spawned while a scratchpad is focused, Hyprland maps it inside the special workspace behind the terminal.
* **Always use `launch <command>`:**
  The `launch` utility automatically targets the focused regular desktop workspace (`[workspace $target_ws]`) and dismisses the special workspace so the app surfaces immediately.
* **Terminal link clicks:**
  Ghostty and CLI link clicks are routed through `~/.local/bin/xdg-open`, which automatically detects scratchpads, handles file extension MIME fixes, and invokes `launch`.

---

## 4. Quickshell Top Bar & Menu Controls

* **Independent Top Bar Font Size:**
  The bar font size is configured independently of global GTK text scaling in `~/.config/omarchy/shell.toml`:
  ```toml
  [bar]
  font-size = 14
  ```
* **Menu Operations:**
  * Toggle menu: `omarchy-menu toggle` (or `SUPER + Space`)
  * Open specific submenu: `omarchy-menu toggle style` or `omarchy-menu summon system`
  * Reload menu JSONC live: `omarchy-menu refresh`
  * Health check: `omarchy-menu ping`

---

## 5. Pointer & Cursor Customization

* **Cursor Speed (Sensitivity):**
  Configured in `~/.config/hypr/hyprland.lua` under `input`:
  ```lua
  input = {
      sensitivity = 0.3, -- Scale from -1.0 (slow) to 1.0 (fast), 0.0 is default
      accel_profile = "adaptive", -- "adaptive" or "flat"
  }
  ```
  Test live without reload: `hyprctl keyword input:sensitivity 0.3`.
* **Cursor Theme & Size:**
  * Apply live:
    ```bash
    hyprctl setcursor Numix-Cursor-Dark 24
    gsettings set org.gnome.desktop.interface cursor-theme "Numix-Cursor-Dark"
    gsettings set org.gnome.desktop.interface cursor-size 24
    ```
  * Persist in `hyprland.lua`:
    ```lua
    hl.env("XCURSOR_THEME", "Numix-Cursor-Dark")
    hl.env("XCURSOR_SIZE", "24")
    hl.env("HYPRCURSOR_THEME", "Numix-Cursor-Dark")
    hl.env("HYPRCURSOR_SIZE", "24")
    ```

---

## 6. Keybindings Reference

| Shortcut | Action |
| :--- | :--- |
| `SUPER + A` | Toggle Antigravity AI terminal scratchpad |
| `SUPER + CTRL + T` | Toggle Activity Monitor (`btop`) scratchpad |
| `SUPER + Space` | Toggle Quickshell application / settings menu |
| `SUPER + T` | Launch main terminal (`kitty`) |
| `SUPER + B` | Launch default browser (`zen-browser` / `firefox`) |
| `SUPER + E` | Open File Manager (`nautilus`) |
| `SUPER + Q` | Close active window |
| `SUPER + F` | Toggle window fullscreen |
| `SUPER + SHIFT + Space` | Toggle window floating |
| `SUPER + C` / `V` / `X` | Universal Copy / Paste / Cut |
| `SUPER + CTRL + V` | Clipboard history (`cliphist`) |
| `PRINT` | Screenshot region to clipboard and file |
| `SUPER + CTRL + PRINT` | OCR screen text snip |
| `SUPER + SHIFT + PRINT` | QR code scanner |
| `SUPER + PRINT` | Color picker (`hyprpicker`) |

---

## 7. Safe Modification & Dotfiles Sync Workflow

1. **Inspect First:** Always view existing config files before editing.
2. **Reload Safely:** After modifying `hyprland.lua`, test and apply with `hyprctl reload`.
3. **Two-Way Git Sync:**
   Whenever live configurations in `~/.config/hypr/`, `~/.config/omarchy/`, or `~/.local/bin/` are modified, always mirror the changes to `~/Arch/arch_install` and commit to the `dev` branch.
4. **Preserve Integrity:** Never execute destructive resets (`rm -rf ~/.config/hypr`, etc.) without explicit user instruction.

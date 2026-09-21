---
name: hyprland-pilot
description: >
  Manage and customize Hyprland desktop environment, Quickshell top bar,
  keybindings, themes, widgets, and desktop configurations on Arch Linux.
  Triggers: Hyprland, hyprland.lua, Quickshell, status bar, themes, wallpapers,
  universal clipboard, keybindings, reminders, OCR, dictation, and monitors.
---

# Hyprland & Quickshell Desktop Pilot Skill

This skill guides the AI assistant when managing, tuning, or troubleshooting the user's
custom Hyprland and Quickshell desktop setup.

## Configuration Layout

* **Hyprland Configuration:** `~/.config/hypr/hyprland.lua`
  * Lua-based Hyprland configuration format (Hyprland 0.56+).
  * Safe reload command: `hyprctl reload`
* **Desktop Shell Configuration:** `~/.config/omarchy/shell.json`
  * Controls the Quickshell top bar layout, position, and active widgets.
  * Shell files live at `~/.local/share/omarchy/shell` (symlinked from `~/.config/quickshell`).
  * IPC command to communicate with running shell: `qs ipc call -- shell ping`
  * Toggle top-bar menu: `qs ipc call -- shell toggle omarchy.menu '{}'`
* **Themes & Wallpapers:** `~/.local/share/omarchy/themes/`
  * Theme switcher: `omarchy-theme-set <name>` (e.g. `tokyo-night`, `catppuccin`, `nord`, `everforest`, `gruvbox`).
* **Active State:** `~/.local/state/omarchy/current/` (contains current theme symlinks and wallpaper).

## Core Keybindings & Architecture Guidelines

* **Universal Clipboard:**
  * `SUPER + C`: Sends `Ctrl + Insert` in terminals, and `Ctrl + C` in GUI windows.
  * `SUPER + V`: Sends `Shift + Insert` in terminals, and `Ctrl + V` in GUI windows.
  * `SUPER + CTRL + V`: Clipboard manager (`cliphist` / Wofi).
* **System Controls:**
  * `SUPER + SPACE`: Toggle Quickshell application and settings menu.
  * `SUPER + R`: Wofi application launcher (`wofi --show drun`).
  * `SUPER + Q`: Launch terminal (`ghostty`).
  * `SUPER + C`: Close active window (`killactive`).
  * `SUPER + L`: Layout switcher / toggle.
  * `SUPER + SHIFT + CTRL + A`: Launch Antigravity CLI in floating window.
* **Capture & OCR:**
  * `PRINT`: Screenshot region to clipboard and file.
  * `SUPER + CTRL + PRINT`: OCR region text extraction to clipboard.
* **Dictation:**
  * `F9` (push-to-talk) / `SUPER + CTRL + X` (toggle): VoxType local speech-to-text.

## Safe Modification Workflow

1. Always inspect existing configuration with read tools before editing.
2. When modifying `~/.config/hypr/hyprland.lua`, test syntax and run `hyprctl reload`.
3. When updating widgets in `~/.config/omarchy/shell.json`, verify JSON validity before saving.
4. Never execute destructive resets unless explicitly requested by the user.

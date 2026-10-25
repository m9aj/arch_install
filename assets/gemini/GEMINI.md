# Arch Install Workspace & Synchronization Rules

## System Modification & Synchronization Policy

Whenever system-level modifications are made to the running machine outside of the `arch_install` repository, the user MUST be prompted with the choice to persist and synchronize those changes into this repository.

### When to Prompt
Proactively ask the user whenever you:
1. **Install, remove, or update packages** (`pacman`, `paru`, `yay`, `flatpak`, etc.).
2. **Modify system configurations** in `/etc/` (`/etc/hosts`, `/etc/fstab`, network configurations, systemd services, udev rules, etc.).
3. **Change desktop environment settings**:
   - GNOME settings via `gsettings` or `dconf`.
   - Application grid launchers, hidden apps (`NoDisplay=true`), dock favorites, or app folders.
   - GNOME Shell extensions.
   - Hyprland Lua settings, window rules, keybindings, or Quickshell top bar configurations.
4. **Modify dotfiles or user scripts** (`~/.config/*`, `~/.local/bin/*`, shell configs).
5. **Adjust network, firewall, Tailscale, or mount point configurations**.

### How to Prompt
At the end of your response after applying the change, always ask clearly:
> *"I've applied this change to your system. Would you like me to update the `arch_install` repository (`/home/ajay/Projects/arch_install`) with this change?"*

Specify the target file and section in `arch_install` that corresponds to the change, using the [`arch-install-pilot`](file:///home/ajay/Projects/arch_install/assets/gemini/skills/arch-install-pilot/SKILL.md) skill for the subsystem mapping.

#!/usr/bin/env python3
import subprocess
import yaml
import sys
import os

# Keys and schemas that change constantly or are handled elsewhere in the installer
IGNORE_PATTERNS = [
    # UI State / Noise
    "window-state", "window-size", "window-position", "window-maximized",
    "last-window-maximised", "last-window-size", "window-height", "window-width",
    "sidebar-width", "paned-position", "maximized", "fullscreen",
    "last-location", "recent-files", "saved-state", "last-panel", "state.window", "last-selected-power-profile", "welcome-dialog-last-shown-version"
    
    # Handled by other parts of the installer (base.yaml logic)
    "app-picker-layout", "enabled-extensions", 
    "favorite-apps", "app-folders", "custom-keybinding",
    
    # Schemas to skip entirely (or broad categories)
    "org.gnome.desktop.input-sources",
    "org.gnome.desktop.notifications",
    "org.gnome.gnome-system-monitor",
    "org.gnome.mutter.wayland",
    "org.gnome.nautilus.window-state",
    "org.gnome.portal.filechooser",
    "org.gnome.settings-daemon.plugins.housekeeping",
    "org.gnome.control-center",
    "org.gnome.nautilus.preferences",
    "org.gnome.settings-daemon.plugins.media-keys",
    "org.gnome.shell", # Disable for extention settings    
]

def parse_dconf_dump():
    try:
        # dconf dump / returns ONLY modified settings in an INI-like format
        dump = subprocess.check_output(["dconf", "dump", "/"]).decode()
    except Exception as e:
        print(f"Error running dconf dump: {e}")
        return {}

    data = {}
    current_schema = None
    
    for line in dump.splitlines():
        line = line.strip()
        if not line:
            continue
            
        # [org/gnome/desktop/interface] -> org.gnome.desktop.interface
        if line.startswith("[") and line.endswith("]"):
            path = line[1:-1].strip("/")
            current_schema = path.replace("/", ".")
            
            # Skip entire schema if it matches ignore patterns
            if any(p in current_schema for p in IGNORE_PATTERNS):
                current_schema = None
                continue

            if current_schema not in data:
                data[current_schema] = {}
        elif "=" in line and current_schema:
            key, value = line.split("=", 1)
            key = key.strip()
            
            # Filter out noise/keys
            if any(p in key for p in IGNORE_PATTERNS):
                continue

            # Values are already in gsettings-compatible format (e.g. 'value', true, 1.0)
            data[current_schema][key] = value.strip()
            
    return data

def main():
    if len(sys.argv) > 1:
        out_path = sys.argv[1]
    else:
        out_path = "dconf_filtered.yaml"
        
    data = parse_dconf_dump()
    
    if not data:
        print("No modified dconf settings found.")
        return

    # Filter out some common noise if desired (optional)
    # e.g. keys that change constantly like 'window-state' or 'last-location'
    
    with open(out_path, "w") as f:
        f.write("# Modified dconf settings (converted from dconf dump /)\n")
        
        # Manually dump each schema to add a newline between them
        schemas = sorted(data.keys())
        for i, schema in enumerate(schemas):
            schema_data = {schema: data[schema]}
            yaml.dump(schema_data, f, default_flow_style=False, sort_keys=True)
            if i < len(schemas) - 1:
                f.write("\n")
        
    print(f"Successfully dumped modified settings to {out_path}")

if __name__ == "__main__":
    main()

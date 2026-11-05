#!/usr/bin/env python3
"""Download, patch, and install Impasto (packages, Hyprland, and Quickshell).

Default workflow (when run with no flags):
  1. Clone https://github.com/andreumassanet/impasto.git into ./impasto (alongside patch-impasto.py)
     (or fetch + reset to latest origin/main if it already exists)
  2. Patch packages/pacman.txt and packages/aur.txt in the cloned repo
  3. Patch home/.config/hypr and home/.config/quickshell in the cloned repo
  4. Run ./setup from the cloned repo
  5. Ensure ~/.config/hypr and ~/.config/quickshell have all patches applied

Usage:
    ./patch-impasto.py                  # Full workflow: download -> patch -> ./setup
    ./patch-impasto.py --unattended     # Full workflow with: ./setup install --skip-system --aur-helper paru --noconfirm
    ./patch-impasto.py --patch-only     # Download/update repo and apply patches without running ./setup
    ./patch-impasto.py --check          # Dry-run check of current patch status in ~/.config
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
IMPASTO_GIT_URL = "https://github.com/andreumassanet/impasto.git"
CURSOR_GIT_URL = "https://github.com/javigomezo/bibata-modern-classic-hyprcursor"
DEFAULT_REPO_DIR = SCRIPT_DIR / "impasto"

DISABLED_PACMAN_PACKAGES = [
    "fnm",
    "yazi",
    "imv",
    "mpv",
    "asciiquarium",
    "neovim",
    "tree-sitter-cli",
    "lua-language-server",
    "pyright",
    "ruff",
    "bash-language-server",
    "sddm",
    "v4l-utils",
    "qemu-desktop",
    "papirus-icon-theme",
]

DISABLED_AUR_PACKAGES = [
    "mpvpaper",
    "wl-screenrec",
    "unimatrix-git",
    "cbonsai",
    "tty-clock",
    "lavat",
    "vscodium-bin",
    "zen-browser-bin",
    "vesktop-bin",
    "spotify",
    "spicetify-cli",
    "quickemu",
]


def download_or_update_repo(repo_dir: Path) -> None:
    """Clone Impasto or reset an existing clone to latest upstream origin/main."""
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    if (repo_dir / ".git").is_dir():
        print(f"==> Updating existing Impasto repository at {repo_dir} ...")
        subprocess.run(["git", "-C", str(repo_dir), "fetch", "origin"], check=True)
        subprocess.run(["git", "-C", str(repo_dir), "reset", "--hard", "origin/main"], check=True)
        subprocess.run(["git", "-C", str(repo_dir), "clean", "-fd"], check=True)
    else:
        if repo_dir.exists():
            shutil.rmtree(repo_dir)
        print(f"==> Cloning Impasto from {IMPASTO_GIT_URL} into {repo_dir} ...")
        subprocess.run(["git", "clone", IMPASTO_GIT_URL, str(repo_dir)], check=True)


def patch_file(path: Path, description: str, marker: str, transform, check_only: bool = False) -> str:
    """Apply `transform(text) -> new_text` to `path` if `marker` is not already present."""
    if not path.exists():
        return f"MISSING: {path} ({description})"

    content = path.read_text(encoding="utf-8")
    if marker in content:
        return f"ALREADY APPLIED: {description} ({path.name})"

    updated = transform(content)
    if updated == content or marker not in updated:
        return f"FAILED TO MATCH TARGET: {description} ({path})"

    if not check_only:
        path.write_text(updated, encoding="utf-8")
    return f"{'WOULD APPLY' if check_only else 'APPLIED'}: {description} ({path.name})"


def disable_packages_in_list(pkg_file: Path, packages: list[str], label: str, check_only: bool) -> str:
    if not pkg_file.exists():
        return f"MISSING: {pkg_file} ({label})"

    content = pkg_file.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    changed = 0
    pkg_set = set(packages)

    new_lines = []
    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        token = stripped.split()[0]
        if token in pkg_set:
            if "  #" in line:
                line = re.sub(rf"^(\s*)({re.escape(token)})(\s\s+)(#.*)$", r"\1# \2\3\4", line)
                line = re.sub(rf"^(\s*# {re.escape(token)})  (\s+#.*)$", r"\1\2", line)
            else:
                line = f"# {line}"
            changed += 1
        new_lines.append(line)

    if changed == 0:
        return f"ALREADY APPLIED: Disable {len(packages)} {label} packages ({pkg_file.name})"

    if not check_only:
        pkg_file.write_text("".join(new_lines), encoding="utf-8")
    return f"{'WOULD APPLY' if check_only else 'APPLIED'}: Disabled {changed} {label} packages ({pkg_file.name})"


def apply_package_patches(repo_dir: Path, check_only: bool) -> list[str]:
    pkg_dir = repo_dir / "packages"
    if not pkg_dir.is_dir():
        return [f"MISSING: {pkg_dir}"]
    return [
        disable_packages_in_list(pkg_dir / "pacman.txt", DISABLED_PACMAN_PACKAGES, "pacman", check_only),
        disable_packages_in_list(pkg_dir / "aur.txt", DISABLED_AUR_PACKAGES, "AUR", check_only),
    ]


def apply_hypr_overrides(config_dir: Path, check_only: bool) -> list[str]:
    results = []
    hypr_dir = config_dir / "hypr"
    src_overrides = SCRIPT_DIR / "user-overrides.lua"
    dst_overrides = hypr_dir / "user-overrides.lua"

    if not hypr_dir.is_dir():
        return [f"MISSING: {hypr_dir}"]

    if dst_overrides.exists() and dst_overrides.read_text(encoding="utf-8") == src_overrides.read_text(encoding="utf-8"):
        results.append("ALREADY APPLIED: Hyprland user-overrides.lua")
    else:
        if not check_only:
            shutil.copy2(src_overrides, dst_overrides)
        results.append(f"{'WOULD APPLY' if check_only else 'APPLIED'}: Hyprland user-overrides.lua")

    hyprland_lua = hypr_dir / "hyprland.lua"
    results.append(
        patch_file(
            hyprland_lua,
            'Hook require("user-overrides") in hyprland.lua',
            'require("user-overrides")',
            lambda text: text.rstrip() + '\n\n-- Personal overrides (scaling, touchpad, Citrix rules)\nrequire("user-overrides")\n',
            check_only,
        )
    )
    return results


def apply_launcher_patches(config_dir: Path, check_only: bool) -> list[str]:
    launcher_qml = config_dir / "quickshell" / "bar" / "island" / "LauncherPanel.qml"
    old_block = """        boundsBehavior: Flickable.StopAtBounds
        // The delegate paints the selection itself; no separate highlight.
        currentIndex: 0

        delegate: Rectangle {
            id: row

            required property var modelData
            required property int index

            // Pointer and keyboard share one selection, so Enter always runs
            // what is lit.
            readonly property bool selected: ListView.view.currentIndex === row.index

            width: ListView.view.width
            height: LauncherService.rowHeight
            radius: Theme.radiusSmall
            color: row.selected ? Theme.surfaceHoverIn(QsWindow.window) : "transparent"

            Behavior on color { ColorAnimation { duration: Theme.durationFast } }"""

    new_block = """        boundsBehavior: Flickable.StopAtBounds
        currentIndex: 0

        highlightFollowsCurrentItem: false
        highlight: Rectangle {
            width: resultList.width
            height: resultList.currentItem ? resultList.currentItem.height : LauncherService.rowHeight
            y: resultList.currentItem ? resultList.currentItem.y : 0
            radius: Theme.radiusSmall
            color: Theme.surfaceHoverIn(QsWindow.window)
            visible: resultList.count > 0

            Behavior on y {
                NumberAnimation {
                    duration: Theme.durationMedium
                    easing.type: Theme.easing
                }
            }
        }

        add: Transition {
            NumberAnimation {
                property: "opacity"
                from: 0
                to: 1
                duration: Theme.durationFast
                easing.type: Theme.easing
            }
        }

        remove: Transition {
            NumberAnimation {
                property: "opacity"
                from: 1
                to: 0
                duration: Theme.durationFast
                easing.type: Theme.easing
            }
        }

        move: Transition {
            NumberAnimation {
                property: "y"
                duration: Theme.durationMedium
                easing.type: Theme.easing
            }
            NumberAnimation {
                property: "opacity"
                to: 1
                duration: Theme.durationFast
                easing.type: Theme.easing
            }
        }

        addDisplaced: Transition {
            NumberAnimation {
                property: "y"
                duration: Theme.durationMedium
                easing.type: Theme.easing
            }
            NumberAnimation {
                property: "opacity"
                to: 1
                duration: Theme.durationFast
                easing.type: Theme.easing
            }
        }

        displaced: Transition {
            NumberAnimation {
                property: "y"
                duration: Theme.durationMedium
                easing.type: Theme.easing
            }
            NumberAnimation {
                property: "opacity"
                to: 1
                duration: Theme.durationFast
                easing.type: Theme.easing
            }
        }

        delegate: Rectangle {
            id: row

            required property var modelData
            required property int index

            // Pointer and keyboard share one selection, so Enter always runs
            // what is lit.
            readonly property bool selected: ListView.view.currentIndex === row.index

            width: ListView.view.width
            height: LauncherService.rowHeight
            radius: Theme.radiusSmall
            color: "transparent\""""

    return [
        patch_file(
            launcher_qml,
            "Smooth animated selection highlight & list transitions in LauncherPanel.qml",
            "highlightFollowsCurrentItem: false",
            lambda text: text.replace(old_block, new_block),
            check_only,
        )
    ]


def apply_power_profile_patches(config_dir: Path, check_only: bool) -> list[str]:
    results = []
    qs_dir = config_dir / "quickshell"

    system_py = qs_dir / "scripts" / "system.py"
    results.append(
        patch_file(
            system_py,
            "3-way power profile cycle (power-saver -> balanced -> performance)",
            '"power-saver": "balanced"',
            lambda text: text.replace(
                'target_profile = "balanced" if current == "performance" else "performance"',
                'cycle = {"power-saver": "balanced", "balanced": "performance", "performance": "power-saver"}\n'
                '        target_profile = cycle.get(current, "balanced")',
            ),
            check_only,
        )
    )

    controls_qml = qs_dir / "services" / "ControlsService.qml"
    old_toggle = """        Toggle {
            key: "power"; icon: "󰓅"; label: "Power"
            detail: SystemService.powerProfile || "Unknown"
            active: SystemService.performanceMode
            available: SystemService.ready
            action: () => SystemService.toggle("power-profile")
        }"""
    new_toggle = """        Toggle {
            key: "power"
            icon: SystemService.powerProfile === "power-saver" ? "󰌪"
                : SystemService.powerProfile === "performance" ? "󰓅" : "󰾅"
            label: "Power"
            detail: SystemService.powerProfile || "Unknown"
            active: SystemService.powerProfile !== "power-saver"
            available: SystemService.ready
            action: () => SystemService.toggle("power-profile")
        }"""
    results.append(
        patch_file(
            controls_qml,
            "3-way Power toggle UI in ControlsService.qml",
            'SystemService.powerProfile === "power-saver" ? "󰌪"',
            lambda text: text.replace(old_toggle, new_toggle),
            check_only,
        )
    )

    battery_qml = qs_dir / "services" / "BatteryService.qml"
    old_battery = """    readonly property bool charging: root.state === UPowerDeviceState.Charging
    readonly property bool full: root.state === UPowerDeviceState.FullyCharged
    readonly property bool low: root.available && !root.charging && !root.full && root.percent <= 20"""
    new_battery = """    readonly property bool charging: root.state === UPowerDeviceState.Charging
    readonly property bool full: root.state === UPowerDeviceState.FullyCharged
    readonly property bool discharging: root.state === UPowerDeviceState.Discharging
    readonly property bool onBattery: root.available && root.discharging
    readonly property bool low: root.onBattery && root.percent <= 20

    // Automatically adjust power profile and turn off keyboard backlight when
    // switching between AC and battery power.
    readonly property Process powerAction: Process {
        onExited: SystemService.refresh()
    }

    onOnBatteryChanged: {
        if (!root.available)
            return
        if (root.onBattery) {
            root.powerAction.command = [
                "sh", "-c",
                "powerprofilesctl set power-saver; brightnessctl --quiet --device='*kbd_backlight*' set 0"
            ]
        } else {
            root.powerAction.command = ["powerprofilesctl", "set", "performance"]
        }
        root.powerAction.running = true
    }

    Component.onCompleted: {
        if (!root.available)
            return
        root.powerAction.command = root.onBattery
            ? ["sh", "-c", "powerprofilesctl set power-saver; brightnessctl --quiet --device='*kbd_backlight*' set 0"]
            : ["powerprofilesctl", "set", "performance"]
        root.powerAction.running = true
    }"""

    def transform_battery(text: str) -> str:
        if "import Quickshell.Io" not in text:
            text = text.replace("import Quickshell\n", "import Quickshell\nimport Quickshell.Io\n", 1)
        return text.replace(old_battery, new_battery)

    results.append(
        patch_file(
            battery_qml,
            "Automatic AC/Battery power profile & keyboard backlight switching",
            "onOnBatteryChanged:",
            transform_battery,
            check_only,
        )
    )
    return results


def apply_theme_manager_patches(config_dir: Path, check_only: bool) -> list[str]:
    results = []
    theme_py = config_dir / "quickshell" / "scripts" / "theme_manager.py"

    old_gtk3_line = "searchbar, actionbar, infobar, statusbar, notebook > header,"
    new_gtk3_line = "searchbar, actionbar, infobar, statusbar, notebook, notebook > stack, notebook > header,"

    old_write_gtk_end = """        except OSError as error:
            sys.stderr.write(f"Cannot write {path}: {error}\\n")


def icon_source_root():"""

    new_write_gtk_end = """        except OSError as error:
            sys.stderr.write(f"Cannot write {path}: {error}\\n")

    subprocess.run(["dconf", "write", "/org/gnome/desktop/interface/gtk-theme", "'Adwaita'"],
                   stderr=subprocess.DEVNULL)
    # Disable LibreOffice's hardcoded per-module Notebookbar tint (Calc=Green, Writer=Blue)
    lo_xcu = os.path.join(XDG_CONFIG_HOME, "libreoffice", "4", "user", "registrymodifications.xcu")
    if os.path.exists(lo_xcu):
        try:
            with open(lo_xcu, encoding="utf-8") as handle:
                xcu = handle.read()
            if "NotebookbarColorTransparency" not in xcu and "</oor:items>" in xcu:
                rule = '<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="NotebookbarColorTransparency" oor:op="fuse"><value>255</value></prop></item>\\n</oor:items>'
                with open(lo_xcu, "w", encoding="utf-8") as handle:
                    handle.write(xcu.replace("</oor:items>", rule, 1))
        except OSError:
            pass
    # If no Nautilus window is open on screen, stop any lingering background
    # D-Bus service so the next window launched reads the new gtk.css.
    try:
        clients = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=2).stdout
        if "org.gnome.Nautilus" not in clients:
            subprocess.run(["pkill", "-x", "nautilus"], stderr=subprocess.DEVNULL)
    except Exception:
        pass


def icon_source_root():"""

    old_dconf_only = """    subprocess.run(["dconf", "write", "/org/gnome/desktop/interface/gtk-theme", "'Adwaita'"],
                   stderr=subprocess.DEVNULL)"""
    new_dconf_with_lo = """    subprocess.run(["dconf", "write", "/org/gnome/desktop/interface/gtk-theme", "'Adwaita'"],
                   stderr=subprocess.DEVNULL)
    # Disable LibreOffice's hardcoded per-module Notebookbar tint (Calc=Green, Writer=Blue)
    lo_xcu = os.path.join(XDG_CONFIG_HOME, "libreoffice", "4", "user", "registrymodifications.xcu")
    if os.path.exists(lo_xcu):
        try:
            with open(lo_xcu, encoding="utf-8") as handle:
                xcu = handle.read()
            if "NotebookbarColorTransparency" not in xcu and "</oor:items>" in xcu:
                rule = '<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="NotebookbarColorTransparency" oor:op="fuse"><value>255</value></prop></item>\\n</oor:items>'
                with open(lo_xcu, "w", encoding="utf-8") as handle:
                    handle.write(xcu.replace("</oor:items>", rule, 1))
        except OSError:
            pass"""

    def transform_gtk(text: str) -> str:
        text = text.replace(old_gtk3_line, new_gtk3_line)
        if old_write_gtk_end in text:
            return text.replace(old_write_gtk_end, new_write_gtk_end)
        return text.replace(old_dconf_only, new_dconf_with_lo)

    results.append(
        patch_file(
            theme_py,
            "GTK/Nautilus reload & LibreOffice GTK3 Notebookbar styling",
            "NotebookbarColorTransparency",
            transform_gtk,
            check_only,
        )
    )

    adwaita_icon_fn = '''ADWAITA_SWATCHES = {
    "Adwaita-Blue-Default": "#62a0ea",
    "Adwaita-Green":        "#55a263",
    "Adwaita-Orange":       "#ef7123",
    "Adwaita-Pink":         "#da77a7",
    "Adwaita-Purple":       "#a05bb7",
    "Adwaita-Red":          "#e94a5c",
    "Adwaita-Slate":        "#8394a4",
    "Adwaita-Teal":         "#409fb0",
    "Adwaita-Yellow":       "#cf9823",
}


def write_icon_theme(colors):
    """Select the Adwaita-* folder icon theme closest to the accent colour."""
    accent = colors.get("accent", "#62a0ea")
    available = {
        name: hex_val
        for name, hex_val in ADWAITA_SWATCHES.items()
        if os.path.isdir(os.path.join(XDG_DATA_HOME, "icons", name))
    }
    chosen = nearest_swatch(accent, available) if available else "Adwaita"
    if not chosen:
        chosen = "Adwaita"

    for gtk_dir in (GTK3_DIR, GTK4_DIR):
        ini_path = os.path.join(gtk_dir, "settings.ini")
        if os.path.exists(ini_path):
            try:
                with open(ini_path, encoding="utf-8") as handle:
                    content = handle.read()
                updated = re.sub(
                    r"^gtk-icon-theme-name=.*$",
                    f"gtk-icon-theme-name={chosen}",
                    content,
                    flags=re.MULTILINE,
                )
                with open(ini_path, "w", encoding="utf-8") as handle:
                    handle.write(updated)
            except OSError:
                pass

    subprocess.run(
        ["dconf", "write", "/org/gnome/desktop/interface/icon-theme", f"'{chosen}'"],
        stderr=subprocess.DEVNULL,
    )
    return True'''

    def replace_write_icon_theme(text: str) -> str:
        pattern = re.compile(
            r"^def write_icon_theme\(colors\):.*?^    return True$",
            re.MULTILINE | re.DOTALL,
        )
        return pattern.sub(adwaita_icon_fn, text, count=1)

    results.append(
        patch_file(
            theme_py,
            "Dynamic Adwaita-* 3D folder icon theme matching wallpaper accent",
            "ADWAITA_SWATCHES",
            replace_write_icon_theme,
            check_only,
        )
    )

    return results


def apply_notification_focus_patches(config_dir: Path, check_only: bool) -> list[str]:
    results = []
    qs_dir = config_dir / "quickshell"

    hypr_service = qs_dir / "services" / "HyprlandService.qml"
    old_focus_win = """    function focusWindow(address: string): void {
        Hyprland.dispatch(`hl.dsp.focus({ window = "address:${address}" })`)
    }"""
    new_focus_win = """    function focusWindow(address: string): void {
        Hyprland.dispatch(`hl.dsp.focus({ window = "address:${address}" })`)
    }

    property var pendingFocusQuery: null

    readonly property Process focusNotificationProcess: Process {
        command: ["hyprctl", "clients", "-j"]
        stdout: StdioCollector {
            onStreamFinished: {
                const query = root.pendingFocusQuery
                root.pendingFocusQuery = null
                if (!query)
                    return
                const list = root.parseJson(text)
                if (!Array.isArray(list))
                    return
                const match = root.matchNotificationClient(list, query)
                if (match && typeof match.address === "string" && match.address !== "")
                    root.focusWindow(match.address)
            }
        }
    }

    function focusNotificationApp(appName: string, desktopEntry: string, summary: string): void {
        const entry = appName ? DesktopEntries.heuristicLookup(appName) : null
        root.pendingFocusQuery = {
            appName: (appName ?? "").trim().toLowerCase(),
            desktopEntry: (desktopEntry ?? "").trim().toLowerCase(),
            summary: (summary ?? "").trim().toLowerCase(),
            entryId: (entry?.id ?? "").replace(/\\.desktop$/i, "").toLowerCase(),
            entryClass: (entry?.startupClass ?? "").toLowerCase(),
            entryIcon: (entry?.icon ?? "").toLowerCase(),
            entryName: (entry?.name ?? "").toLowerCase()
        }
        root.focusNotificationProcess.running = false
        root.focusNotificationProcess.running = true
    }

    function matchNotificationClient(list: var, query: var): var {
        const candidates = [
            query.appName,
            query.desktopEntry,
            query.entryId,
            query.entryClass,
            query.entryIcon,
            query.entryName
        ].filter(s => s && s.length > 0 && !s.includes("/"))

        const wantsAgy = query.summary.includes("antigravity")
            || query.appName.includes("antigravity")
            || /\\bagy\\b/.test(query.summary)

        let best = null
        let bestScore = 0
        let bestHistory = 999999

        for (const client of list) {
            if (!client.mapped || !client.workspace || client.workspace.id <= 0)
                continue

            const cls = (client.class ?? "").toLowerCase()
            const icls = (client.initialClass ?? "").toLowerCase()
            const title = (client.title ?? "").toLowerCase()
            const ititle = (client.initialTitle ?? "").toLowerCase()
            const historyId = typeof client.focusHistoryID === "number" ? client.focusHistoryID : 999999

            let score = 0

            for (const cand of candidates) {
                if (cls === cand || icls === cand
                        || cls.endsWith("." + cand) || cand.endsWith("." + cls)) {
                    score = Math.max(score, 200)
                } else if (cand.length >= 3 && (cls.includes(cand) || icls.includes(cand))) {
                    score = Math.max(score, 150)
                }
            }

            const cleanTitle = title.split(" — ")[0].trim()
            if (score === 0) {
                for (const cand of candidates) {
                    if (cand.length >= 3 && (ititle === cand || cleanTitle === cand))
                        score = Math.max(score, 180)
                    else if (cand.length >= 4 && (ititle.includes(cand) || cleanTitle.includes(cand)))
                        score = Math.max(score, 120)
                }
                if (cls.startsWith("ffpwa-") && query.summary.length > 0) {
                    if ((ititle.length >= 3 && query.summary.includes(ititle))
                            || (cleanTitle.length >= 3 && query.summary.includes(cleanTitle))) {
                        score = Math.max(score, 220)
                    }
                }
            }

            if (wantsAgy) {
                const isAgyTitle = title === "agy" || ititle === "agy"
                    || /\\bagy\\b/.test(title) || title.includes("antigravity")
                if (isAgyTitle && (score > 0 || cls === "kitty"))
                    score = Math.max(score, 350)
                else if (isAgyTitle)
                    score = Math.max(score, 300)
                else if (cls.includes("antigravity"))
                    score = Math.max(score, 280)
            }

            if (score > 0 && query.summary.length >= 3) {
                if ((cleanTitle.length >= 3 && query.summary.includes(cleanTitle))
                        || (ititle.length >= 3 && query.summary.includes(ititle))
                        || cleanTitle.includes(query.summary)) {
                    score += 50
                }
            }

            if (score > bestScore || (score > 0 && score === bestScore && historyId < bestHistory)) {
                best = client
                bestScore = score
                bestHistory = historyId
            }
        }

        return best
    }"""

    results.append(
        patch_file(
            hypr_service,
            "HyprlandService notification window matching (including Antigravity/agy)",
            "focusNotificationApp(",
            lambda text: text.replace(old_focus_win, new_focus_win),
            check_only,
        )
    )

    notif_service = qs_dir / "services" / "NotificationService.qml"
    old_record = """            appName: notification.appName,
            icon: notification.appIcon || notification.desktopEntry || "","""
    new_record = """            appName: notification.appName,
            desktopEntry: notification.desktopEntry || "",
            icon: notification.appIcon || notification.desktopEntry || "","""

    old_open = """    function invoke(action: var): void {
        if (action)
            action.invoke()
        root.dismiss()
    }

    // An entry in the history, clicked: its notification's default action,
    // while the notification is still open.
    function open(entry: var): bool {
        const action = root.defaultAction(root.openOf(entry))
        if (!action)
            return false
        action.invoke()
        return true
    }"""
    new_open = """    function invoke(action: var): void {
        if (action)
            action.invoke()
        root.dismiss()
    }

    function activate(): void {
        const n = root.current
        if (!n)
            return
        const appName = n.appName ?? ""
        const desktopEntry = n.desktopEntry || n.appIcon || ""
        const summary = n.summary ?? ""
        const action = root.defaultAction(n)
        if (action) {
            action.invoke()
            root.dismiss()
        } else {
            root.close()
        }
        HyprlandService.focusNotificationApp(appName, desktopEntry, summary)
    }

    function canOpen(entry: var): bool {
        if (!entry)
            return false
        if (root.defaultAction(root.openOf(entry)) !== null)
            return true
        return Boolean((entry.appName && entry.appName !== "")
            || (entry.desktopEntry && entry.desktopEntry !== "")
            || (entry.icon && entry.icon !== "")
            || (entry.summary && entry.summary !== ""))
    }

    // An entry in the history, clicked: its notification's default action,
    // while the notification is still open, and focuses the matching window.
    function open(entry: var): bool {
        if (!entry)
            return false
        const action = root.defaultAction(root.openOf(entry))
        if (action)
            action.invoke()
        if (root.current && root.current.id === entry.id)
            root.dismiss()
        HyprlandService.focusNotificationApp(
            entry.appName ?? "",
            entry.desktopEntry || entry.icon || "",
            entry.summary ?? "")
        return true
    }"""

    old_save = """            appName: entry.appName,
            icon: entry.icon ?? "","""
    new_save = """            appName: entry.appName,
            desktopEntry: entry.desktopEntry ?? "",
            icon: entry.icon ?? "","""

    results.append(
        patch_file(
            notif_service,
            "NotificationService activate() and history open() window focusing",
            "function activate(): void",
            lambda text: text.replace(old_record, new_record)
            .replace(old_open, new_open)
            .replace(old_save, new_save),
            check_only,
        )
    )

    notif_layer = qs_dir / "bar" / "island" / "NotificationLayer.qml"
    old_layer_click = """                if (event.button === Qt.LeftButton && root.defaultAction !== null)
                    NotificationService.invoke(root.defaultAction)"""
    new_layer_click = """                if (event.button === Qt.LeftButton)
                    NotificationService.activate()"""
    results.append(
        patch_file(
            notif_layer,
            "NotificationLayer left-click focuses app window",
            "NotificationService.activate()",
            lambda text: text.replace(old_layer_click, new_layer_click),
            check_only,
        )
    )

    notif_list = qs_dir / "bar" / "island" / "controls" / "NotificationList.qml"
    old_list_opens = """                readonly property bool opens: NotificationService.defaultAction(
                    NotificationService.openOf(entry.modelData)) !== null"""
    new_list_opens = """                readonly property bool opens: NotificationService.canOpen(entry.modelData)"""
    results.append(
        patch_file(
            notif_list,
            "NotificationList click focuses app window from history",
            "NotificationService.canOpen(entry.modelData)",
            lambda text: text.replace(old_list_opens, new_list_opens),
            check_only,
        )
    )

    return results


def ensure_settings_json(check_only: bool) -> list[str]:
    """Deploy saved settings.json to ~/.local/state/quickshell/settings.json."""
    src = SCRIPT_DIR / "settings.json"
    if not src.is_file():
        return [f"MISSING: {src} (Saved Quickshell settings.json)"]

    state_home = Path(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")))
    dst = state_home / "quickshell" / "settings.json"

    src_text = src.read_text(encoding="utf-8")
    if dst.is_file() and dst.read_text(encoding="utf-8") == src_text:
        return [f"ALREADY APPLIED: Quickshell settings ({dst})"]

    if check_only:
        return [f"WOULD APPLY: Copy {src.name} -> {dst}"]

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return [f"APPLIED: Restored Quickshell settings ({dst})"]


def ensure_cursor_source(config_dir: Path, check_only: bool) -> list[str]:
    """Ensure ~/.local/state/quickshell/cursor-src exists so cursor color changes work."""
    state_home = Path(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")))
    cursor_src = state_home / "quickshell" / "cursor-src"
    if (cursor_src / "manifest.hl").is_file():
        return [f"ALREADY APPLIED: Vector cursor source at {cursor_src}"]
    if check_only:
        return [f"WOULD APPLY: Clone Bibata vector cursor source to {cursor_src}"]

    if cursor_src.exists():
        shutil.rmtree(cursor_src)
    cursor_src.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", "--depth=1", CURSOR_GIT_URL, str(cursor_src)], check=True)
    compositor_py = config_dir / "quickshell" / "scripts" / "compositor.py"
    if compositor_py.is_file() and shutil.which("hyprcursor-util"):
        subprocess.run(["python3", str(compositor_py), "cursor", "palette", "24", "--seed"], check=False)
    return [f"APPLIED: Cloned Bibata vector cursor source & built impasto-cursor ({cursor_src})"]


def apply_monitor_scale_patch(config_dir: Path, check_only: bool) -> list[str]:
    """Prevent MonitorService.differs() from looping every 600ms on fractional scales like 1.67 vs 1.667."""
    mon_svc = config_dir / "quickshell" / "services" / "MonitorService.qml"
    old = "|| (rule.scale !== undefined && Number(rule.scale) !== Number(found.scale))"
    new = "|| (rule.scale !== undefined && Math.abs(Number(rule.scale) - Number(found.scale)) > 0.01)"
    return [
        patch_file(
            mon_svc,
            "Fractional scale tolerance in MonitorService.qml (prevents 600ms workspace rescue loop)",
            new,
            lambda text: text.replace(old, new, 1),
            check_only,
        )
    ]


def apply_monitor_power_patch(config_dir: Path, check_only: bool) -> list[str]:
    """Add Screen Power toggle to Arrangement tab and enable switch for off/charging displays in MonitorsSection.qml."""
    mon_section = config_dir / "quickshell" / "settings" / "MonitorsSection.qml"
    marker = "label: root.current ? `${root.current.name} · ${Tr.t(\"Power\")}` : Tr.t(\"Screen Power\")"

    old = """                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 14
                        spacing: 10

                        Text {
                            text: "󰶐"
                            font.family: Theme.fontMono
                            font.pixelSize: 12
                            color: root.chosen === dark.modelData.description
                                ? Theme.accent : Theme.textMuted
                        }

                        Text {
                            Layout.fillWidth: true
                            text: Tr.t("%1 — off, and still plugged in").arg(dark.modelData.name)
                            elide: Text.ElideRight
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textMuted
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.chosen = dark.modelData.description
                    }
                }
            }

            SettingRow {
                label: Tr.t("Arrangement")"""

    new = """                    MouseArea {
                        anchors.fill: parent
                        anchors.rightMargin: 60
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.chosen = dark.modelData.description
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 14
                        spacing: 10

                        Text {
                            text: "󰶐"
                            font.family: Theme.fontMono
                            font.pixelSize: 12
                            color: root.chosen === dark.modelData.description
                                ? Theme.accent : Theme.textMuted
                        }

                        Text {
                            Layout.fillWidth: true
                            text: Tr.t("%1 — off, and still plugged in").arg(dark.modelData.name)
                            elide: Text.ElideRight
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.textMuted
                        }

                        ToggleSwitch {
                            checked: false
                            onToggled: checked => {
                                if (checked)
                                    MonitorService.remember(dark.modelData.description, { disabled: false })
                            }
                        }
                    }
                }
            }

            SettingRow {
                visible: !root.single
                label: root.current ? `${root.current.name} · ${Tr.t("Power")}` : Tr.t("Screen Power")
                reading: root.currentOff
                    ? Tr.t("Off — out of layout, still plugged in (e.g. charging)")
                    : Tr.t("On — active in layout")
                locked: root.lastLit
                reason: Tr.t("The only screen there is")

                ToggleSwitch {
                    checked: !root.currentOff
                    onToggled: checked => root.change({ disabled: !checked })
                }
            }

            SettingRow {
                label: Tr.t("Arrangement")"""

    return [
        patch_file(
            mon_section,
            "Screen Power toggle on Arrangement tab in MonitorsSection.qml",
            marker,
            lambda text: text.replace(old, new, 1),
            check_only,
        )
    ]


def apply_caffeine_patch(config_dir: Path, check_only: bool) -> list[str]:
    """Add Caffeine button to Bar Layout Editor, Top Bar, Controls toggles, and Quickshell Commands."""
    results = []

    # 1. IdleService.qml
    idle_file = config_dir / "quickshell" / "services" / "IdleService.qml"
    idle_marker = "property bool caffeine"
    old_idle = """    readonly property IdleMonitor lockWatch: IdleMonitor {
        enabled: root.lockAfter > 0
        timeout: root.lockAfter * 60
        respectInhibitors: true

        // `lock()` is a no-op when already locked.
        onIsIdleChanged: {
            if (lockWatch.isIdle)
                LockService.lock()
        }
    }

    readonly property IdleMonitor screenWatch: IdleMonitor {
        enabled: root.screenAfter > 0
        timeout: root.screenAfter * 60
        respectInhibitors: true
        onIsIdleChanged: root.screen(!screenWatch.isIdle)
    }

    readonly property IdleMonitor sleepWatch: IdleMonitor {
        enabled: root.suspendAfter > 0
        timeout: root.suspendAfter * 60"""

    new_idle = """    // Caffeine: keep screen and system awake.
    property bool caffeine: false

    function toggleCaffeine(): void {
        root.caffeine = !root.caffeine
        if (root.caffeine)
            root.screen(true)
        OsdService.requested(root.caffeine ? "\U000f0176" : "\U000f0faa",
                             root.caffeine ? "Caffeine active" : "Caffeine inactive",
                             -1)
    }

    readonly property IdleMonitor lockWatch: IdleMonitor {
        enabled: !root.caffeine && root.lockAfter > 0
        timeout: root.lockAfter * 60
        respectInhibitors: true

        // `lock()` is a no-op when already locked.
        onIsIdleChanged: {
            if (lockWatch.isIdle)
                LockService.lock()
        }
    }

    readonly property IdleMonitor screenWatch: IdleMonitor {
        enabled: !root.caffeine && root.screenAfter > 0
        timeout: root.screenAfter * 60
        respectInhibitors: true
        onIsIdleChanged: root.screen(!screenWatch.isIdle)
    }

    readonly property IdleMonitor sleepWatch: IdleMonitor {
        enabled: !root.caffeine && root.suspendAfter > 0
        timeout: root.suspendAfter * 60"""

    results.append(
        patch_file(
            idle_file,
            "Caffeine toggle & inhibitor logic in IdleService.qml",
            idle_marker,
            lambda text: text.replace(old_idle, new_idle, 1),
            check_only,
        )
    )

    # 2. ModuleService.qml
    mod_file = config_dir / "quickshell" / "services" / "ModuleService.qml"
    mod_marker = 'out[id] = {\n                    name: "Caffeine",'
    old_mod = """    readonly property var buttonIds: ["launcher", "overview", "controls", "capture",
        "appearance", "notes", "board", "games", "keys", "packages", "settings", "session"]

    readonly property var buttons: {
        const out = {}
        for (const id of root.buttonIds) {
            if (id === "controls") {"""

    new_mod = """    readonly property var buttonIds: ["caffeine", "launcher", "overview", "controls", "capture",
        "appearance", "notes", "board", "games", "keys", "packages", "settings", "session"]

    readonly property var buttons: {
        const out = {}
        for (const id of root.buttonIds) {
            if (id === "caffeine") {
                out[id] = {
                    name: "Caffeine",
                    glyph: IdleService.caffeine ? "\U000f0176" : "\U000f0faa",
                    active: IdleService.caffeine,
                    detail: IdleService.caffeine ? "Sleep disabled" : "Idle sleep enabled",
                    action: () => IdleService.toggleCaffeine()
                }
                continue
            }
            if (id === "controls") {"""

    results.append(
        patch_file(
            mod_file,
            "Caffeine bar button catalogue entry in ModuleService.qml",
            mod_marker,
            lambda text: text.replace(old_mod, new_mod, 1),
            check_only,
        )
    )

    # 3. BarChip.qml
    barchip_file = config_dir / "quickshell" / "bar" / "widgets" / "BarChip.qml"
    barchip_marker = "color: (root.door && root.door.active) ? Theme.accent : Theme.text"
    old_barchip = """    Text {
        anchors.centerIn: parent
        visible: root.button
        text: root.door ? root.door.glyph : ""
        font.family: Theme.fontMono
        font.pixelSize: Math.round(Theme.capsuleHeight * 0.44)
        color: Theme.text
    }"""
    new_barchip = """    Text {
        anchors.centerIn: parent
        visible: root.button
        text: root.door ? root.door.glyph : ""
        font.family: Theme.fontMono
        font.pixelSize: Math.round(Theme.capsuleHeight * 0.44)
        color: (root.door && root.door.active) ? Theme.accent : Theme.text
    }"""

    results.append(
        patch_file(
            barchip_file,
            "Accent color highlight for active buttons in BarChip.qml",
            barchip_marker,
            lambda text: text.replace(old_barchip, new_barchip, 1),
            check_only,
        )
    )

    # 4. ControlsService.qml
    ctrl_file = config_dir / "quickshell" / "services" / "ControlsService.qml"
    ctrl_marker = 'key: "caffeine"'
    old_ctrl = """    readonly property list<QtObject> toggleCatalogue: [
        Toggle {
            key: "wifi"; icon: NetworkService.icon; label: "Wi-Fi\""""

    new_ctrl = """    readonly property list<QtObject> toggleCatalogue: [
        Toggle {
            key: "caffeine"
            icon: IdleService.caffeine ? "\U000f0176" : "\U000f0faa"
            label: "Caffeine"
            detail: IdleService.caffeine ? "Awake" : "Sleep"
            active: IdleService.caffeine
            action: () => IdleService.toggleCaffeine()
        },
        Toggle {
            key: "wifi"; icon: NetworkService.icon; label: "Wi-Fi\""""

    def patch_ctrl(text: str) -> str:
        text = text.replace(old_ctrl, new_ctrl, 1)
        old_def = '["wifi", "bluetooth", "power", "focus", "microphone", "airplane"]'
        new_def = '["wifi", "bluetooth", "caffeine", "power", "focus", "airplane"]'
        return text.replace(old_def, new_def, 1)

    results.append(
        patch_file(
            ctrl_file,
            "Caffeine quick toggle in ControlsService.qml",
            ctrl_marker,
            patch_ctrl,
            check_only,
        )
    )

    # 5. LayoutEditor.qml
    layout_file = config_dir / "quickshell" / "settings" / "LayoutEditor.qml"
    layout_marker = "ModuleService.buttons[chip.entryId].active"
    old_layout1 = """        Text {
            anchors.centerIn: parent
            visible: chip.button
            text: chip.button ? ModuleService.buttons[chip.entryId].glyph : ""
            font.family: Theme.fontMono
            font.pixelSize: Math.round(Theme.capsuleHeight * 0.44)
            color: Theme.text
        }"""
    new_layout1 = """        Text {
            anchors.centerIn: parent
            visible: chip.button
            text: chip.button ? ModuleService.buttons[chip.entryId].glyph : ""
            font.family: Theme.fontMono
            font.pixelSize: Math.round(Theme.capsuleHeight * 0.44)
            color: (chip.button && ModuleService.buttons[chip.entryId] && ModuleService.buttons[chip.entryId].active) ? Theme.accent : Theme.text
        }"""

    old_layout2 = """                // Buttons show their glyph, and so does the tray.
                Text {
                    anchors.centerIn: parent
                    visible: ModuleService.isButton(entry.entryId) || entry.entryId === "tray"
                    text: entry.entryId === "tray" ? root.trayGlyph
                        : visible ? ModuleService.buttons[entry.entryId].glyph : ""
                    font.family: Theme.fontMono
                    font.pixelSize: Math.round(Theme.capsuleHeight * 0.44)
                    color: Theme.text
                }"""
    new_layout2 = """                // Buttons show their glyph, and so does the tray.
                Text {
                    anchors.centerIn: parent
                    visible: ModuleService.isButton(entry.entryId) || entry.entryId === "tray"
                    text: entry.entryId === "tray" ? root.trayGlyph
                        : visible ? ModuleService.buttons[entry.entryId].glyph : ""
                    font.family: Theme.fontMono
                    font.pixelSize: Math.round(Theme.capsuleHeight * 0.44)
                    color: (visible && ModuleService.buttons[entry.entryId] && ModuleService.buttons[entry.entryId].active) ? Theme.accent : Theme.text
                }"""

    def patch_layout(text: str) -> str:
        text = text.replace(old_layout1, new_layout1, 1)
        text = text.replace(old_layout2, new_layout2, 1)
        return text

    results.append(
        patch_file(
            layout_file,
            "Caffeine active preview color in LayoutEditor.qml",
            layout_marker,
            patch_layout,
            check_only,
        )
    )

    # 6. Commands.qml
    cmd_file = config_dir / "quickshell" / "Commands.qml"
    cmd_marker = 'target: "caffeine"'
    old_cmd = '    IpcHandler {\n        target: "lock"'
    new_cmd = """    IpcHandler {
        target: "caffeine"

        function get(): string {
            return root.ok({ caffeine: IdleService.caffeine })
        }

        function toggle(): string {
            IdleService.toggleCaffeine()
            return root.ok({ caffeine: IdleService.caffeine })
        }

        function set(word: string): string {
            const on = root.switched(word, IdleService.caffeine)
            if (on === null)
                return root.fail("on, off or toggle")
            if (on !== IdleService.caffeine)
                IdleService.toggleCaffeine()
            return root.ok({ caffeine: IdleService.caffeine })
        }
    }

    IpcHandler {
        target: "lock\""""

    results.append(
        patch_file(
            cmd_file,
            "Caffeine IPC handler in Commands.qml",
            cmd_marker,
            lambda text: text.replace(old_cmd, new_cmd, 1),
            check_only,
        )
    )

    return results

def patch_config_tree(config_dir: Path, check_only: bool) -> list[str]:
    results = []
    results.extend(apply_hypr_overrides(config_dir, check_only))
    results.extend(apply_monitor_scale_patch(config_dir, check_only))
    results.extend(apply_monitor_power_patch(config_dir, check_only))
    results.extend(apply_launcher_patches(config_dir, check_only))
    results.extend(apply_power_profile_patches(config_dir, check_only))
    results.extend(apply_theme_manager_patches(config_dir, check_only))
    results.extend(apply_notification_focus_patches(config_dir, check_only))
    results.extend(apply_caffeine_patch(config_dir, check_only))
    return results


def print_results(lines: list[str]) -> bool:
    failed = False
    for line in lines:
        print(f"  • {line}")
        if line.startswith(("MISSING:", "FAILED")):
            failed = True
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download Impasto, apply personal patches, and run ./setup."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=DEFAULT_REPO_DIR,
        help=f"Impasto git clone location (default: {DEFAULT_REPO_DIR})",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))),
        help="Target .config directory (default: ~/.config)",
    )
    parser.add_argument(
        "--patch-only",
        action="store_true",
        help="Download/update Impasto repo and apply patches without running ./setup",
    )
    parser.add_argument(
        "--unattended",
        action="store_true",
        help="Run ./setup install --skip-system --aur-helper paru --noconfirm non-interactively",
    )
    parser.add_argument(
        "--setup-args",
        type=str,
        default=None,
        help='Custom arguments to pass to ./setup (e.g. "install --skip-system")',
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Dry-run check of current patch status without modifying files",
    )
    parser.add_argument(
        "--save-settings",
        action="store_true",
        help="Save live ~/.local/state/quickshell/settings.json to Projects/hyprland/settings.json",
    )
    args = parser.parse_args()

    if args.save_settings:
        state_home = Path(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")))
        live = state_home / "quickshell" / "settings.json"
        dst = SCRIPT_DIR / "settings.json"
        if not live.is_file():
            sys.stderr.write(f"ERROR: Live settings not found at {live}\n")
            return 1
        shutil.copy2(live, dst)
        print(f"==> Saved live settings from {live} -> {dst}")
        return 0

    repo = args.repo.expanduser().resolve()
    target = args.target.expanduser().resolve()
    failed = False

    # Mode 1: Dry-run check or --patch-only
    if args.check or args.patch_only:
        if args.patch_only:
            download_or_update_repo(repo)
        if repo.is_dir() and (repo / "packages").is_dir():
            print(f"==> Checking/patching Impasto repo: {repo}")
            failed |= print_results(apply_package_patches(repo, args.check))
            repo_cfg = repo / "home" / ".config"
            if repo_cfg.is_dir():
                failed |= print_results(patch_config_tree(repo_cfg, args.check))
        if target.is_dir() and ((target / "quickshell").is_dir() or (target / "hypr").is_dir() or args.check):
            print(f"\n==> Checking/patching live config: {target}")
            failed |= print_results(patch_config_tree(target, args.check))
            failed |= print_results(ensure_settings_json(args.check))
            failed |= print_results(ensure_cursor_source(target, args.check))
        return 1 if failed else 0

    # Mode 2: Full workflow (Download/Update -> Patch Repo -> Run ./setup -> Verify Live ~/.config)
    download_or_update_repo(repo)

    print(f"\n==> Patching Impasto repository at {repo} ...")
    failed |= print_results(apply_package_patches(repo, False))
    failed |= print_results(patch_config_tree(repo / "home" / ".config", False))
    if failed:
        sys.stderr.write("\nERROR: One or more patches failed to apply to the repository. Aborting ./setup.\n")
        return 1

    setup_script = repo / "setup"
    if not setup_script.exists():
        sys.stderr.write(f"ERROR: {setup_script} not found.\n")
        return 1

    if args.setup_args is not None:
        setup_cmd = [str(setup_script)] + args.setup_args.split()
    elif args.unattended:
        setup_cmd = [str(setup_script), "install", "--skip-system", "--aur-helper", "paru", "--noconfirm"]
    else:
        setup_cmd = [str(setup_script)]

    print(f"\n==> Launching Impasto setup: {' '.join(setup_cmd)}\n")
    result = subprocess.run(setup_cmd, cwd=str(repo))
    if result.returncode != 0:
        return result.returncode

    if target.is_dir() and (target / "quickshell").is_dir():
        print(f"\n==> Verifying live config at {target} ...")
        failed |= print_results(patch_config_tree(target, False))
        failed |= print_results(ensure_settings_json(False))
        failed |= print_results(ensure_cursor_source(target, False))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

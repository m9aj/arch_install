------------------------------------------------------------
-- Hyprland Configuration (Lua format for Hyprland 0.56+)
------------------------------------------------------------

local home = os.getenv("HOME") or "/home/ajay"

------------------
---- MONITORS ----
------------------
local monitors_config = home .. "/.config/hypr/monitors.lua"
local f_mon = io.open(monitors_config, "r")
if f_mon then
    f_mon:close()
    dofile(monitors_config)
else
    hl.monitor({
        output   = "",
        mode     = "preferred",
        position = "auto",
        scale    = 1.6,
    })
end

---------------------
---- MY PROGRAMS ----
---------------------
local terminal = "ghostty"
local fileManager = "nautilus"
local menu = "wofi --show drun"

-------------------
---- AUTOSTART ----
-------------------
hl.on("hyprland.start", function () 
    hl.exec_cmd("systemctl --user import-environment WAYLAND_DISPLAY DISPLAY XDG_CURRENT_DESKTOP OMARCHY_PATH PATH")
    hl.exec_cmd("dbus-update-activation-environment --systemd --all")
    hl.exec_cmd("quickshell -d -n -p " .. home .. "/.local/share/omarchy/shell")
    hl.exec_cmd("/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1")
    hl.exec_cmd("wl-paste --type text --watch cliphist store")
    hl.exec_cmd("wl-paste --type image --watch cliphist store")
    hl.exec_cmd("hyprsunset")
end)

-------------------------------
---- ENVIRONMENT VARIABLES ----
-------------------------------
hl.env("OMARCHY_PATH", home .. "/.local/share/omarchy")
hl.env("PATH", home .. "/.local/share/omarchy/bin:" .. (os.getenv("PATH") or ""))
hl.env("OMARCHY_SCREENSHOT_DIR", home .. "/Pictures/Screenshots")
hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")
hl.env("QT_QPA_PLATFORM", "wayland")
hl.env("GDK_BACKEND", "wayland,x11")

------------------------------
---- LOOK & FEEL SETTINGS ----
------------------------------
hl.config({
    general = {
        gaps_in  = 4,
        gaps_out = 8,
        border_size = 2,
        col = {
            active_border   = { colors = {"rgba(7aa2f7ee)", "rgba(bb9af7ee)"}, angle = 45 },
            inactive_border = "rgba(414868aa)",
        },
        resize_on_border = true,
        allow_tearing    = false,
        layout           = "dwindle",
    },

    decoration = {
        rounding       = 10,
        active_opacity = 1.0,
        inactive_opacity = 0.95,

        shadow = {
            enabled      = true,
            range        = 4,
            render_power = 3,
            color        = 0xee1a1a1a,
        },

        blur = {
            enabled  = true,
            size     = 5,
            passes   = 2,
            vibrancy = 0.1696,
        },
    },

    animations = {
        enabled = true,
    },

    dwindle = {
        preserve_split = true,
    },

    misc = {
        force_default_wallpaper = 0,
        disable_hyprland_logo   = true,
        vrr                     = 1, -- 0 = off, 1 = on, 2 = fullscreen only
    },

    input = {
        kb_layout    = "us",
        follow_mouse = 1,
        sensitivity  = 0,
        touchpad = {
            natural_scroll       = true,
            clickfinger_behavior = true,
        },
    },

    xwayland = {
        force_zero_scaling = true,
    },
})

--------------------
---- ANIMATIONS ----
--------------------
hl.curve("easeOutQuint",   { type = "bezier", points = { {0.23, 1},    {0.32, 1}    } })
hl.curve("easeInOutCubic", { type = "bezier", points = { {0.65, 0.05}, {0.36, 1}    } })
hl.curve("linear",         { type = "bezier", points = { {0, 0},       {1, 1}       } })
hl.curve("almostLinear",   { type = "bezier", points = { {0.5, 0.5},   {0.75, 1}    } })
hl.curve("quick",          { type = "bezier", points = { {0.15, 0},    {0.1, 1}     } })

hl.animation({ leaf = "global",        enabled = true,  speed = 10,   bezier = "default" })
hl.animation({ leaf = "border",        enabled = true,  speed = 5.39, bezier = "easeOutQuint" })
hl.animation({ leaf = "windows",       enabled = true,  speed = 4.79, bezier = "easeOutQuint" })
hl.animation({ leaf = "windowsIn",     enabled = true,  speed = 4.1,  bezier = "easeOutQuint", style = "popin 87%" })
hl.animation({ leaf = "windowsOut",    enabled = true,  speed = 1.49, bezier = "linear",       style = "popin 87%" })
hl.animation({ leaf = "fadeIn",        enabled = true,  speed = 1.73, bezier = "almostLinear" })
hl.animation({ leaf = "fadeOut",       enabled = true,  speed = 1.46, bezier = "almostLinear" })
hl.animation({ leaf = "fade",          enabled = true,  speed = 3.03, bezier = "quick" })
hl.animation({ leaf = "layers",        enabled = true,  speed = 3.81, bezier = "easeOutQuint" })
hl.animation({ leaf = "workspaces",    enabled = true,  speed = 1.94, bezier = "almostLinear", style = "fade" })

----------------------------
---- UNIVERSAL CLIPBOARD ---
----------------------------
local function send_shortcut_once(mods, key)
    return function()
        hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "down" }))
        hl.timer(function()
            hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "up" }))
        end, { timeout = 50, type = "oneshot" })
    end
end

local function active_window_is_terminal()
    local window = hl.get_active_window()
    if not window then return false end
    for _, tag in ipairs(window.tags or {}) do
        if tag:gsub("%*$", "") == "terminal" then return true end
    end
    local class = window.class or ""
    if class:match("kitty") or class:match("ghostty") or class:match("foot") or class:match("Alacritty") or class:match("org.gnome.Console") then
        return true
    end
    return false
end

local function universal_clipboard(default_mods, default_key, terminal_mods, terminal_key)
    return function()
        if active_window_is_terminal() then
            send_shortcut_once(terminal_mods, terminal_key)()
        else
            send_shortcut_once(default_mods, default_key)()
        end
    end
end

----------------------
---- KEYBINDINGS -----
----------------------
local mainMod = "SUPER"

-- Help & Shortcuts Cheat Sheet
hl.bind(mainMod .. " + F1",    hl.dsp.exec_cmd("omarchy-menu-keybindings"), { description = "Keybindings" })

-- Universal Copy, Paste & Cut
hl.bind(mainMod .. " + C", universal_clipboard("CTRL", "C", "CTRL+SHIFT", "C"), { description = "Universal copy" })
hl.bind(mainMod .. " + V", universal_clipboard("CTRL", "V", "CTRL+SHIFT", "V"), { description = "Universal paste" })
hl.bind(mainMod .. " + X", send_shortcut_once("CTRL", "X"),                     { description = "Universal cut" })
hl.bind(mainMod .. " + CTRL + V", hl.dsp.exec_cmd("cliphist list | wofi --dmenu --prompt 'Clipboard' | cliphist decode | wl-copy"), { description = "Clipboard history" })

-- Menus & Launchers
hl.bind(mainMod .. " + Space", hl.dsp.exec_cmd("quickshell ipc -p " .. home .. "/.local/share/omarchy/shell call shell toggle omarchy.menu '{}'"), { description = "Launcher menu" })
hl.bind(mainMod .. " + R", hl.dsp.exec_cmd(menu), { description = "Launch apps" })
hl.bind(mainMod .. " + T", hl.dsp.exec_cmd(terminal), { description = "Terminal" })
hl.bind(mainMod .. " + B", hl.dsp.exec_cmd("firefox"), { description = "Browser" })
hl.bind(mainMod .. " + I", hl.dsp.exec_cmd("firefox --private-window"), { description = "Browser (incognito)" })
hl.bind(mainMod .. " + E", hl.dsp.exec_cmd(fileManager), { description = "File manager" })
hl.bind(mainMod .. " + W", hl.dsp.exec_cmd("omarchy-menu-wallpaper"), { description = "Wallpaper menu" })
hl.bind(mainMod .. " + SHIFT + T", hl.dsp.exec_cmd("omarchy-menu-theme"), { description = "Theme menu" })
hl.bind(mainMod .. " + Q", hl.dsp.window.close(), { description = "Close window" })
hl.bind(mainMod .. " + M", hl.dsp.exit(), { description = "Exit Hyprland" })
hl.bind(mainMod .. " + SHIFT + Space", hl.dsp.window.float({ action = "toggle" }), { description = "Toggle window floating" })
hl.bind(mainMod .. " + F", hl.dsp.window.fullscreen(), { description = "Toggle fullscreen" })
hl.bind(mainMod .. " + S", hl.dsp.layout("togglesplit"), { description = "Toggle window split" })

-- AI Integration (Antigravity CLI in floating window)
hl.bind(mainMod .. " + A", hl.dsp.workspace.toggle_special("antigravity"), { description = "Antigravity AI" })

-- System & TUIs
hl.bind(mainMod .. " + CTRL + T", hl.dsp.workspace.toggle_special("btop"), { description = "Activity monitor (btop)" })
hl.bind(mainMod .. " + SHIFT + R", hl.dsp.exec_cmd("omarchy-reminder -i"), { description = "Reminders" })
hl.bind(mainMod .. " + CTRL + N", hl.dsp.exec_cmd("toggle-nightlight"), { description = "Toggle nightlight" })
hl.bind(mainMod .. " + SHIFT + B", hl.dsp.exec_cmd("toggle-bar"), { description = "Toggle top bar" })
hl.bind(mainMod .. " + SHIFT + N", hl.dsp.exec_cmd("toggle-dnd"), { description = "Silence notifications" })
hl.bind(mainMod .. " + SHIFT + W", hl.dsp.exec_cmd("toggle-stay-awake"), { description = "Toggle stay awake" })

-- Notices & Quick Panels
hl.bind(mainMod .. " + CTRL + ALT + T", hl.dsp.exec_cmd("omarchy-notification-time"),    { description = "Date & time notice" })
hl.bind(mainMod .. " + CTRL + ALT + B", hl.dsp.exec_cmd("omarchy-notification-battery"), { description = "Battery notice" })
hl.bind(mainMod .. " + CTRL + ALT + W", hl.dsp.exec_cmd("omarchy-notification-weather"), { description = "Weather notice" })
hl.bind(mainMod .. " + CTRL + ALT + D", hl.dsp.exec_cmd("quickshell ipc -p " .. home .. "/.local/share/omarchy/shell call shell toggle omarchy.clock '{}'"),     { description = "Calendar panel" })
hl.bind(mainMod .. " + CTRL + A",       hl.dsp.exec_cmd("quickshell ipc -p " .. home .. "/.local/share/omarchy/shell call shell toggle omarchy.audio '{}'"),     { description = "Audio controls" })
hl.bind(mainMod .. " + CTRL + B",       hl.dsp.exec_cmd("quickshell ipc -p " .. home .. "/.local/share/omarchy/shell call shell toggle omarchy.bluetooth '{}'"), { description = "Bluetooth controls" })
hl.bind(mainMod .. " + CTRL + D",       hl.dsp.exec_cmd("quickshell ipc -p " .. home .. "/.local/share/omarchy/shell call shell toggle omarchy.monitor '{}'"),   { description = "Display panel" })
hl.bind(mainMod .. " + CTRL + W",       hl.dsp.exec_cmd("quickshell ipc -p " .. home .. "/.local/share/omarchy/shell call shell toggle omarchy.network '{}'"),   { description = "Wifi controls" })
hl.bind(mainMod .. " + CTRL + P",       hl.dsp.exec_cmd("quickshell ipc -p " .. home .. "/.local/share/omarchy/shell call shell toggle omarchy.power '{}'"),     { description = "Power menu panel" })

-- Screenshots & OCR (Native Wayland)
hl.bind("PRINT", hl.dsp.exec_cmd("screenshot"), { description = "Screenshot" })
hl.bind(mainMod .. " + CTRL + PRINT", hl.dsp.exec_cmd("ocr-snip"), { description = "OCR screen text" })
hl.bind(mainMod .. " + SHIFT + PRINT", hl.dsp.exec_cmd("qr-scan"), { description = "Scan QR code" })
hl.bind(mainMod .. " + PRINT", hl.dsp.exec_cmd("pkill hyprpicker || hyprpicker -a"), { description = "Color picker" })

-- Hardware Audio & Brightness Controls
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"), { locked = true, repeating = true, description = "Volume up" })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"),      { locked = true, repeating = true, description = "Volume down" })
hl.bind("XF86AudioMute",        hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"),     { locked = true, repeating = true, description = "Mute audio" })
hl.bind("XF86AudioMicMute",     hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"),   { locked = true, repeating = true, description = "Mute microphone" })
hl.bind("XF86MonBrightnessUp",  hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%+"),                  { locked = true, repeating = true, description = "Brightness up" })
hl.bind("XF86MonBrightnessDown",hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%-"),                  { locked = true, repeating = true, description = "Brightness down" })
hl.bind("XF86AudioNext",        hl.dsp.exec_cmd("playerctl next"),                                 { locked = true, description = "Next track" })
hl.bind("XF86AudioPause",       hl.dsp.exec_cmd("playerctl play-pause"),                           { locked = true, description = "Play/pause media" })
hl.bind("XF86AudioPlay",        hl.dsp.exec_cmd("playerctl play-pause"),                           { locked = true, description = "Play/pause media" })
hl.bind("XF86AudioPrev",        hl.dsp.exec_cmd("playerctl previous"),                             { locked = true, description = "Previous track" })

-- Focus & Window Navigation (Arrow Keys)
hl.bind(mainMod .. " + left",  hl.dsp.focus({ direction = "left" }),  { description = "Focus window left" })
hl.bind(mainMod .. " + right", hl.dsp.focus({ direction = "right" }), { description = "Focus window right" })
hl.bind(mainMod .. " + up",    hl.dsp.focus({ direction = "up" }),    { description = "Focus window up" })
hl.bind(mainMod .. " + down",  hl.dsp.focus({ direction = "down" }),  { description = "Focus window down" })

-- Move / Swap Windows (Arrow Keys)
hl.bind(mainMod .. " + SHIFT + left",  hl.dsp.window.move({ direction = "left" }),  { description = "Swap window left" })
hl.bind(mainMod .. " + SHIFT + right", hl.dsp.window.move({ direction = "right" }), { description = "Swap window right" })
hl.bind(mainMod .. " + SHIFT + up",    hl.dsp.window.move({ direction = "up" }),    { description = "Swap window up" })
hl.bind(mainMod .. " + SHIFT + down",  hl.dsp.window.move({ direction = "down" }),  { description = "Swap window down" })

-- Mouse Window Drag & Resize
hl.bind(mainMod .. " + mouse:272", hl.dsp.window.drag(),   { mouse = true, description = "Move window" })
hl.bind(mainMod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true, description = "Resize window" })

-- Workspace Navigation (1-9)
for i = 1, 9 do
    hl.bind(mainMod .. " + " .. i,         hl.dsp.focus({ workspace = i }),        { description = "Switch to workspace " .. i })
    hl.bind(mainMod .. " + SHIFT + " .. i, hl.dsp.window.move({ workspace = i }), { description = "Move window to workspace " .. i })
end

----------------------
---- WINDOW RULES ----
----------------------
hl.window_rule({
    name  = "suppress-maximize-events",
    match = { class = ".*" },
    suppress_event = "maximize",
})

hl.window_rule({
    name  = "fix-xwayland-drags",
    match = {
        class      = "^$",
        title      = "^$",
        xwayland   = true,
        float      = true,
        fullscreen = false,
        pin        = false,
    },
    no_focus = true,
})

hl.window_rule({
    name  = "terminals",
    match = { class = "^(kitty|ghostty|foot|Alacritty|org.gnome.Console|.*floating.*)$" },
    tag   = "terminal",
})

hl.window_rule({
    name  = "webapps",
    match = { class = "^(FFPWA-.*)$" },
    tag   = "webapp",
})

hl.window_rule({
    name   = "floating-windows",
    match  = { class = ".*floating.*" },
    float  = true,
    size   = { 1350, 880 },
    center = true,
})

hl.window_rule({
    name        = "citrix-epic",
    match       = { class = "^(Hyperspace.*)$" },
    border_size = 0,
    rounding    = 0,
})

hl.window_rule({
    name        = "citrix-wfica",
    match       = { class = "^(.*wfica.*|.*Citrix.*)$" },
    border_size = 0,
    rounding    = 0,
})

-------------------------
---- WORKSPACE RULES ----
-------------------------
hl.workspace_rule({
    workspace        = "special:btop",
    on_created_empty = "ghostty --class=com.floating.btop -e btop",
})

hl.workspace_rule({
    workspace        = "special:antigravity",
    on_created_empty = "ghostty --class=com.floating.antigravity -e " .. home .. "/.local/bin/agy",
})

------------------
---- GESTURES ----
------------------
-- 3-finger horizontal swipe to switch workspaces
hl.gesture({
    fingers   = 3,
    direction = "horizontal",
    action    = "workspace",
})

-- 3-finger swipe up to toggle fullscreen
hl.gesture({
    fingers   = 3,
    direction = "up",
    action    = "fullscreen",
})

-- 2-finger pinch in/out to toggle fullscreen
hl.gesture({
    fingers   = 2,
    direction = "pinch",
    action    = "fullscreen",
})





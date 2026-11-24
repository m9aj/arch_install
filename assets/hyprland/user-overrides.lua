-- ╭──────────────────────────────────────────────────────────────────────────╮
-- │                                                                          │
-- │   U S E R   O V E R R I D E S                                            │
-- │   Personal hardware and window rule overrides for Hyprland / Impasto     │
-- │                                                                          │
-- ╰──────────────────────────────────────────────────────────────────────────╯

-- 1. Monitor scaling (Managed via Impasto UI / MonitorService)
-- hl.monitor({
--     output   = "",
--     mode     = "preferred",
--     position = "auto",
--     scale    = 1.67,
-- })

-- 2. Touchpad & pointer speed + Native XWayland scaling
hl.config({
    input = {
        sensitivity   = 0.3,
        accel_profile = "adaptive",
        touchpad      = {
            natural_scroll = true,
            scroll_factor  = 1.0,
        },
    },
    xwayland = {
        force_zero_scaling = true,
    },
})

-- 3. Set 150% X11 DPI (144) so XWayland apps (Citrix) scale natively at 2880x1920
hl.exec_cmd("xprop -root -f RESOURCE_MANAGER 8s -set RESOURCE_MANAGER 'Xft.dpi:\t144\n'")
hl.on("hyprland.start", function()
    hl.exec_cmd("xprop -root -f RESOURCE_MANAGER 8s -set RESOURCE_MANAGER 'Xft.dpi:\t144\n'")
end)

-- 4. Allow Citrix / Epic Hyperspace / Hyperdrive maximize events (override upstream rule)
hl.window_rule({
    name  = "suppress-maximize-events",
    match = { class = "negative:^(wfica|Wfica|Hyperspace.*|Hyperdrive.*|[Cc]itrix.*|[Ss]elfservice)$" },

    suppress_event = "maximize",
})

-- 5. Citrix Workspace / Epic Hyperspace Window Rules
--    - Float all XWayland / Citrix child windows (Dragon Medical One, MF_systray, popups)
--      so they keep their native widget size.
--    - Keep the main Epic Hyperspace window tiled at full workspace size.
--    - Remove rounded corners, transparency, and blur on all Citrix windows.
hl.window_rule({
    name  = "citrix-children-float",
    match = { xwayland = true },

    float    = true,
    opaque   = true,
    no_blur  = true,
    rounding = 0,
})

hl.window_rule({
    name  = "citrix-hyperspace-main",
    match = {
        class    = "^Hyperspace.*$",
        xwayland = true,
    },

    tile     = true,
    opaque   = true,
    no_blur  = true,
    rounding = 0,
})


-- 6. Custom Keybindings (loaded dynamically from custom-keybindings.lua if present)
pcall(require, "custom-keybindings")

-- 7. PWA Custom Window Border Colors
hl.window_rule({
    name         = "pwa-whatsapp-border",
    match        = { class = "^FFPWA-01KYKCWQYKGQ5NT68W2FC88V2Q$" },
    border_color = "rgb(25D366) rgb(128C7E)",
})

hl.window_rule({
    name         = "pwa-messages-border",
    match        = { class = "^FFPWA-01KYKD71MMBSANDW29ZQ3GK6PE$" },
    border_color = "rgb(38bdf8) rgb(0284c7)",
})

-- 8. Firefox, Outlook & Citrix PWA Password Manager & Extension Popouts (float immediately with zero flicker)
local browser_and_outlook_class = "^(firefox|org\\.mozilla\\.firefox|FFPWA-01KYKC8DGJ8KVZJA0FWYQHX5DG|FFPWA-01KYKCFVSDKCGXT6WFFNG7QY30|FFPWA-01KYK98VFAZ2GMZJ67TPRW591H)$"

local function is_firefox_or_outlook_pwa(cls)
    local c = (cls or ""):lower()
    return c:find("firefox")
        or c:find("org.mozilla.firefox")
        or c == "ffpwa-01kykc8dgj8kvzja0fwyqhx5dg" -- Outlook Sound
        or c == "ffpwa-01kykcfvsdkcgxt6wffng7qy30" -- Outlook Prov
        or c == "ffpwa-01kyk98vfaz2gmzj67tprw591h" -- Citrix
end

hl.window_rule({
    name  = "firefox-bitwarden-float",
    match = {
        class = browser_and_outlook_class,
        title = ".*Bitwarden.*",
    },

    float  = true,
    center = true,
    size   = {460, 660},
})

-- 9. GNOME / GTK Headerbar Buttons: Remove close, minimize, and maximize buttons in Hyprland
hl.exec_cmd("gsettings set org.gnome.desktop.wm.preferences button-layout ':'")
hl.on("hyprland.start", function()
    hl.exec_cmd("gsettings set org.gnome.desktop.wm.preferences button-layout ':'")
end)


hl.window_rule({
    name  = "firefox-extension-float",
    match = {
        class = browser_and_outlook_class,
        title = "Extension: .*",
    },

    float  = true,
    center = true,
    size   = {460, 660},
})

-- Prevent tiling flicker: float secondary Firefox / Outlook PWA windows immediately upon creation
hl.on("window.open", function(w)
    local raw_class = w.class or ""
    if not is_firefox_or_outlook_pwa(raw_class) then return end

    local match_class = raw_class:lower():find("firefox") and "firefox" or raw_class
    local app_windows = hl.get_windows({ class = match_class })
    if #app_windows <= 1 then return end

    -- Float immediately upon spawn so it never splits or flickers the main window
    hl.dispatch(hl.dsp.window.float({ action = "set", window = w }))

    local sub
    local done = false
    local function resolve(tw, title)
        if done then return end
        done = true
        if sub then sub:remove() end

        if title:match("^Extension:") or title:match("Bitwarden") or title:match("About Logins") or title:match("Passwords") then
            hl.dispatch(hl.dsp.window.resize({ x = 460, y = 660, window = tw }))
            hl.dispatch(hl.dsp.window.center({ window = tw }))
            hl.dispatch(hl.dsp.focus({ window = tw }))
        else
            -- Normal browser window (e.g. Ctrl+N / New Tab), restore tiling
            hl.dispatch(hl.dsp.window.float({ action = "unset", window = tw }))
        end
    end

    sub = hl.on("window.title", function(tw)
        if tw.address ~= w.address then return end
        local title = tw.title or ""
        if title == ""
            or title == "Mozilla Firefox"
            or title == "Outlook Sound"
            or title == "Outlook Prov"
            or title == "Citrix"
            or title == "about:blank"
            or title:match("^about:.*") then
            return
        end
        resolve(tw, title)
    end)

    hl.timer(350, function()
        if not done then
            local cur = hl.get_window({ address = w.address }) or w
            resolve(cur, cur.title or "")
        end
    end)
end)

-- Fallback safety net for existing or retitled extension windows
hl.on("window.title", function(w)
    local title = w.title or ""
    if title:match("^Extension:") or title:match("Bitwarden") or title:match("About Logins") or title:match("Passwords") then
        if is_firefox_or_outlook_pwa(w.class) and not w.floating then
            hl.dispatch(hl.dsp.window.float({ action = "set", window = w }))
            hl.dispatch(hl.dsp.window.resize({ x = 460, y = 660, window = w }))
            hl.dispatch(hl.dsp.window.center({ window = w }))
            hl.dispatch(hl.dsp.focus({ window = w }))
        end
    end
end)


-- 10. Workspace Assignment Rules
--     - Workspace 1: Todo and Calendar
--     - Workspace 2: Firefox (startup window only, handled in section 11)
--     - Workspace 5: Messages and WhatsApp
hl.window_rule({
    name      = "pwa-todo-workspace",
    match     = { class = "^FFPWA-01KYKD44VJAES35FFZ52PDF3XD$" },
    workspace = "1",
})

hl.window_rule({
    name      = "pwa-calendar-workspace",
    match     = { class = "^FFPWA-01M46PZY404S71WYYV92TXMZXD$" },
    workspace = "1",
})

hl.window_rule({
    name      = "pwa-messages-workspace",
    match     = { class = "^FFPWA-01KYKD71MMBSANDW29ZQ3GK6PE$" },
    workspace = "5",
})

hl.window_rule({
    name      = "pwa-whatsapp-workspace",
    match     = { class = "^FFPWA-01KYKCWQYKGQ5NT68W2FC88V2Q$" },
    workspace = "5",
})

-- 11. Autostart Applications on Hyprland Launch
hl.on("hyprland.start", function()
    -- Launch background communication apps on workspace 5
    hl.exec_cmd("firefoxpwa site launch 01KYKD71MMBSANDW29ZQ3GK6PE") -- Messages
    hl.exec_cmd("firefoxpwa site launch 01KYKCWQYKGQ5NT68W2FC88V2Q") -- WhatsApp

    -- Move only the initial startup Firefox window to workspace 2
    local ff_sub
    ff_sub = hl.on("window.open", function(w)
        local cls = (w.class or ""):lower()
        if cls == "firefox" or cls == "org.mozilla.firefox" then
            ff_sub:remove()
            hl.dispatch(hl.dsp.window.move({ workspace = 2, window = "address:" .. w.address, follow = false }))
        end
    end)
    hl.exec_cmd("firefox")

    -- Launch productivity apps on workspace 1
    hl.exec_cmd("firefoxpwa site launch 01M46PZY404S71WYYV92TXMZXD") -- Calendar
    hl.exec_cmd("firefoxpwa site launch 01KYKD44VJAES35FFZ52PDF3XD") -- Todo
end)

-- 12. Gemini Launcher Shortcut (SUPER + G)
hl.unbind("SUPER + G")
hl.bind("SUPER + G", hl.dsp.exec_cmd("gtk-launch gemini"), { description = "Applications · Open Gemini" })

-- 13. Cycle Split Ratio (SUPER + R): Left/Top 2/3 -> Right/Bottom 2/3 -> Equal 50/50
local split_ratios = { 1.333, 0.667, 1.0 }
local split_state = {}

hl.bind("SUPER + R", function()
    local ws = hl.get_active_workspace()
    local id = ws and ws.id or 0
    local next_idx = ((split_state[id] or 0) % #split_ratios) + 1
    split_state[id] = next_idx
    local delta = split_ratios[next_idx] - 0.1
    hl.dispatch(hl.dsp.layout("splitratio -2.0"))
    hl.dispatch(hl.dsp.layout(string.format("splitratio +%.3f", delta)))
end, { description = "Windows · Cycle split ratio (2/3, 1/3, 50/50)" })

-- 14. Disable accidental DPMS screen-off shortcut (SUPER + SHIFT + D)
hl.unbind("SUPER + SHIFT + D")

-- 15. Let Hyprland handle the power button (open session menu instead of logind powering off)
hl.on("hyprland.start", function()
    hl.exec_cmd("pkill -f 'systemd-inhibit --what=handle-power-key --who=hyprland' || true; systemd-inhibit --what=handle-power-key --who=hyprland --why='Session menu handles power key' sleep infinity")
end)






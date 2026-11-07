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

-- 8. Firefox Password Manager & Extension Popouts (float immediately with zero flicker)
hl.window_rule({
    name  = "firefox-bitwarden-float",
    match = {
        class = "^(firefox|org\\.mozilla\\.firefox)$",
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
        class = "^(firefox|org\\.mozilla\\.firefox)$",
        title = "Extension: .*",
    },

    float  = true,
    center = true,
    size   = {460, 660},
})

-- Prevent tiling flicker: float secondary Firefox windows immediately upon creation
hl.on("window.open", function(w)
    local class = (w.class or ""):lower()
    if not (class:find("firefox") or class:find("org.mozilla.firefox")) then return end

    local ff_windows = hl.get_windows({ class = "firefox" })
    if #ff_windows <= 1 then return end

    -- Float immediately upon spawn so it never splits or flickers the main window
    hl.dispatch(hl.dsp.window.float({ action = "set", window = w }))

    local sub
    sub = hl.on("window.title", function(tw)
        if tw.address ~= w.address then return end
        local title = tw.title or ""
        if title == ""
            or title == "Mozilla Firefox"
            or title == "about:blank"
            or title:match("^about:.*Mozilla Firefox$") then
            return
        end

        sub:remove()

        if title:match("^Extension:") or title:match("Bitwarden") or title:match("About Logins") or title:match("Passwords") then
            hl.dispatch(hl.dsp.window.resize({ x = 460, y = 660, window = tw }))
            hl.dispatch(hl.dsp.window.center({ window = tw }))
            hl.dispatch(hl.dsp.focus({ window = tw }))
        else
            -- Normal browser window (e.g. Ctrl+N), restore tiling
            hl.dispatch(hl.dsp.window.float({ action = "unset", window = tw }))
        end
    end)
end)

-- Fallback safety net for existing or retitled extension windows
hl.on("window.title", function(w)
    local title = w.title or ""
    if title:match("^Extension:") or title:match("Bitwarden") or title:match("About Logins") or title:match("Passwords") then
        local class = (w.class or ""):lower()
        if (class:find("firefox") or class:find("org.mozilla.firefox")) and not w.floating then
            hl.dispatch(hl.dsp.window.float({ action = "set", window = w }))
            hl.dispatch(hl.dsp.window.resize({ x = 460, y = 660, window = w }))
            hl.dispatch(hl.dsp.window.center({ window = w }))
            hl.dispatch(hl.dsp.focus({ window = w }))
        end
    end
end)





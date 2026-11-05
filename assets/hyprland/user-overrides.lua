-- ╭──────────────────────────────────────────────────────────────────────────╮
-- │                                                                          │
-- │   U S E R   O V E R R I D E S                                            │
-- │   Personal hardware and window rule overrides for Hyprland / Impasto     │
-- │                                                                          │
-- ╰──────────────────────────────────────────────────────────────────────────╯

-- 1. Monitor scaling (Framework 13 2.8K @ 1.67x)
hl.monitor({
    output   = "",
    mode     = "preferred",
    position = "auto",
    scale    = 1.67,
})

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

-- 3. Set 167% X11 DPI (160) so XWayland apps (Citrix) scale natively at 2880x1920
hl.exec_cmd("xprop -root -f RESOURCE_MANAGER 8s -set RESOURCE_MANAGER 'Xft.dpi:\t160\n'")
hl.on("hyprland.start", function()
    hl.exec_cmd("xprop -root -f RESOURCE_MANAGER 8s -set RESOURCE_MANAGER 'Xft.dpi:\t160\n'")
end)

-- 4. Allow Citrix / Epic Hyperspace / Hyperdrive maximize events (override upstream rule)
hl.window_rule({
    name  = "suppress-maximize-events",
    match = { class = "negative:^(wfica|Wfica|Hyperspace.*|Hyperdrive.*|[Cc]itrix.*|[Ss]elfservice)$" },

    suppress_event = "maximize",
})

-- 5. Citrix Workspace / Epic Hyperspace / Hyperdrive Window Rules
--    - Float and center all Citrix dialogs & child windows (Dragon Medical One, logon dialogs, popups)
--      so they are always visible on-screen and keep their native size.
--    - Tile the main Epic Hyperspace / Hyperdrive application window at full workspace size.
--    - Remove rounded corners, transparency, and blur on all Citrix windows.
hl.window_rule({
    name  = "citrix-children-float",
    match = {
        class    = "^(wfica|Wfica|[Cc]itrix.*)$",
        xwayland = true,
    },

    float    = true,
    center   = true,
    opaque   = true,
    no_blur  = true,
    rounding = 0,
})

hl.window_rule({
    name  = "citrix-hyperspace-main",
    match = {
        class    = "^(wfica|Wfica|[Cc]itrix.*)$",
        title    = "^(Hyperspace|Hyperdrive).*$",
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

-- 8. Firefox Password Manager & Extension Popouts (float instead of tiling)
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

-- Dynamic event listener: Catches Firefox popup windows when title updates dynamically
local function auto_float_firefox_popups(w)
    if not w then return end
    local class = tostring(w.class or ""):lower()
    local title = tostring(w.title or "")
    if class == "firefox" or class == "org.mozilla.firefox" then
        if title:find("Bitwarden") or title:find("Extension:") or title:find("Password") or title:find("About Logins") then
            local addr = tostring(w.address or "")
            if not addr:find("^0x") then
                addr = "0x" .. addr
            end
            hl.dispatch(hl.dsp.focus({ window = "address:" .. addr }))
            hl.dispatch(hl.dsp.window.float({ action = "set" }))
            hl.dispatch(hl.dsp.window.resize({ x = 460, y = 660 }))
            hl.dispatch(hl.dsp.window.center())
        end
    end
end

hl.on("window.title", auto_float_firefox_popups)
hl.on("window.open", auto_float_firefox_popups)




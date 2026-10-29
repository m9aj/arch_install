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

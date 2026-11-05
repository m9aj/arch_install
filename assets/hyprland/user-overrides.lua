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

    local resolved = false
    local sub = nil

    local function resolve(is_extension, target_win)
        if resolved then return end
        resolved = true
        if sub then
            sub:remove()
            sub = nil
        end

        local win = target_win or hl.get_window("address:" .. w.address)
        if not win then return end

        if is_extension then
            hl.dispatch(hl.dsp.window.resize({ x = 460, y = 660, window = win }))
            hl.dispatch(hl.dsp.window.center({ window = win }))
            hl.dispatch(hl.dsp.focus({ window = win }))
        else
            -- Normal browser window (e.g. Ctrl+N or dragged tab), restore tiling
            hl.dispatch(hl.dsp.window.float({ action = "unset", window = win }))
        end
    end

    sub = hl.on("window.title", function(tw)
        if tw.address ~= w.address then return end
        local title = tw.title or ""
        if title:match("^Extension:") or title:match("Bitwarden") or title:match("About Logins") or title:match("Passwords") then
            resolve(true, tw)
        elseif title ~= "" and title ~= "Mozilla Firefox" and title ~= "about:blank" then
            -- Distinct webpage title (e.g. tab drag or loaded URL), tile immediately
            resolve(false, tw)
        end
    end)

    -- Fallback timer: if after 350ms the window still hasn't become an extension, tile it
    hl.timer(function()
        if not resolved then
            local cur = hl.get_window("address:" .. w.address)
            if cur then
                local t = cur.title or ""
                if t:match("^Extension:") or t:match("Bitwarden") or t:match("About Logins") or t:match("Passwords") then
                    resolve(true, cur)
                else
                    resolve(false, cur)
                end
            end
        end
    end, { timeout = 350, type = "oneshot" })
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





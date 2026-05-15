# core/resolver.py

import hashlib
import json
import subprocess
from core.helper_core import load_yaml

_resolve_cache = {}

_profiles = load_yaml("package_profiles.yaml")
CORE_PROFILES = _profiles.get("core_profiles", {})
POST_PROFILES = _profiles.get("post_profiles", {})
INIT_PACKAGES = _profiles.get("init_packages", {})
BOOTLOADER_CFG = _profiles.get("bootloader", {})

# ------------------------
# Hardware Detection
# ------------------------

_NOT_CACHED = object()
_cpu_cache = _NOT_CACHED
_gpu_cache = _NOT_CACHED


def detect_cpu():
    global _cpu_cache
    if _cpu_cache is not _NOT_CACHED:
        return _cpu_cache
    result = None
    try:
        out = subprocess.check_output(["lscpu"]).decode().lower()
        if "intel" in out:
            result = "intel"
        elif "amd" in out:
            result = "amd"
    except Exception:
        pass
    _cpu_cache = result
    return result


def detect_gpu():
    global _gpu_cache
    if _gpu_cache is not _NOT_CACHED:
        return _gpu_cache
    result = None
    try:
        out = subprocess.check_output(["lspci"]).decode().lower()
        if "nvidia" in out:
            result = "nvidia"
        elif "amd" in out:
            result = "amd"
    except Exception:
        pass
    _gpu_cache = result
    return result

# ------------------------
# Package Profile Resolution
# ------------------------

def hardware_profile(config):
    core_pkgs = []
    post_pkgs = []

    cpu_cfg = config["hardware"].get("cpu", "auto")
    gpu_cfg = config["hardware"].get("gpu", "auto")

    cpu = detect_cpu() if cpu_cfg == "auto" else cpu_cfg
    gpu = detect_gpu() if gpu_cfg == "auto" else gpu_cfg

    # CPU → core
    if cpu == "intel":
        core_pkgs.append("intel-ucode")
    elif cpu == "amd":
        core_pkgs.append("amd-ucode")

    # GPU → post
    if gpu == "nvidia":
        post_pkgs.append("nvidia-open")
        post_pkgs.append("libva-nvidia-driver")
    elif gpu == "amd":
        post_pkgs.append("xf86-video-amdgpu")

    return {
        "core": core_pkgs,
        "post": post_pkgs
    }


def boot_profile(config):
    core_pkgs = []
    services = []

    boot_cfg = config.get("boot", {})

    # init
    init = boot_cfg.get("init", "mkinitcpio")
    core_pkgs += INIT_PACKAGES.get(init, [])

    # bootloader
    bootloader = boot_cfg.get("bootloader", "systemd-boot")
    bl_profile = BOOTLOADER_CFG.get(bootloader, {})
    
    # New format: dict with packages, services, kernel_params
    core_pkgs += bl_profile.get("packages", [])
    services += bl_profile.get("services", [])

    # From config directly
    kernel_params = boot_cfg.get("kernel_params", [])

    return {
        "core": core_pkgs,
        "services": services,
        "kernel_params": kernel_params
    }

def resolve_system(config):
    """
    Resolves the core system (profiles + hardware + boot).
    Does NOT include features, as they are handled exclusively in Phase 2.
    """
    cache_key = hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()[:16]
    if cache_key in _resolve_cache:
        return _resolve_cache[cache_key]

    core_pkgs = []
    post_pkgs = []
    services = []
    sysctl = {}
    kernel_params = []

    # core
    for p in config["pkgprofile"].get("core", []):
        core_pkgs += CORE_PROFILES.get(p, [])

    # post
    pkg_cfg = config.get("pkgprofile", {})
    for p in pkg_cfg.get("post", []):
        profile = POST_PROFILES.get(p, {})
        post_pkgs += profile.get("packages", [])
        services += profile.get("services", [])
        kernel_params += profile.get("kernel_params", [])
        sysctl.update(profile.get("sysctl", {}))

    # machine_specific overrides
    ms_cfg = config.get("machine_specific", {})
    post_pkgs += ms_cfg.get("pacman", [])
    services += ms_cfg.get("services", [])

    # Hardware Logic
    hw = hardware_profile(config)
    core_pkgs += hw["core"]
    post_pkgs += hw["post"]

    # Init/Boot Logic
    boot = boot_profile(config)
    core_pkgs += boot["core"]
    services += boot.get("services", [])
    kernel_params += boot.get("kernel_params", [])

    # DE auto
    de = config["arch"].get("de")
    if de in POST_PROFILES:
        profile = POST_PROFILES[de]
        post_pkgs += profile.get("packages", [])
        services += profile.get("services", [])
        kernel_params += profile.get("kernel_params", [])

    result = {
        "core": dedupe(core_pkgs),
        "post": dedupe(post_pkgs),
        "services": dedupe(services),
        "sysctl": sysctl,
        "kernel_params": dedupe(kernel_params),
    }
    _resolve_cache[cache_key] = result
    return result


def dedupe(pkgs):
    return list(dict.fromkeys(pkgs))

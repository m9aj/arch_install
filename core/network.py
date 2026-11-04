# core/network.py

import glob
import os
import re
import shlex
import time
from core.shell import run
from core.logger import logger


def check_internet():
    # Try hostname first; fall back to reliable public DNS IP if DNS is not yet ready
    result = run("ping -c 1 -W 3 google.com", check=False)
    if result.returncode == 0:
        return True
    result_ip = run("ping -c 1 -W 3 1.1.1.1", check=False)
    return result_ip.returncode == 0


def detect_wifi_interface():
    result = run("iwctl device list", check=False)
    ansi_escape = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
    for line in result.stdout.splitlines():
        clean_line = ansi_escape.sub("", line)
        parts = clean_line.split()
        if parts and parts[0].startswith("wl"):
            return parts[0]

    for path in sorted(glob.glob("/sys/class/net/*")):
        if os.path.exists(os.path.join(path, "wireless")) or os.path.exists(os.path.join(path, "phy80211")):
            return os.path.basename(path)

    return "wlan0"


def connect_wifi(config):
    wifi_data = config.get("network", {}).get("wifi", {})

    # Support either a single dict or a list of WiFi network dicts
    if isinstance(wifi_data, list):
        networks = wifi_data
    elif isinstance(wifi_data, dict):
        if "networks" in wifi_data and isinstance(wifi_data["networks"], list):
            networks = wifi_data["networks"]
        elif wifi_data.get("ssid"):
            networks = [wifi_data]
        else:
            networks = []
    else:
        networks = []

    if not networks:
        logger.warning("No WiFi networks configured in network.wifi")
        return False

    # Attempt connection to configured networks in order
    for net in networks:
        ssid = net.get("ssid")
        if not ssid:
            continue
        ssid = str(ssid).strip()
        password = net.get("password")
        interface = str(net.get("interface") or detect_wifi_interface())

        logger.info(f"Connecting to WiFi: '{ssid}' on {interface}")

        if password is not None and str(password) != "":
            password_str = str(password)
            result = run(
                f"iwctl --passphrase {shlex.quote(password_str)} station {shlex.quote(interface)} connect {shlex.quote(ssid)}",
                check=False,
                log_cmd=False,
            )
        else:
            result = run(
                f"iwctl station {shlex.quote(interface)} connect {shlex.quote(ssid)}",
                check=False,
            )

        if result.returncode == 0:
            logger.info("Waiting for connection...")
            time.sleep(4)
            if check_internet():
                return True

    return False


def ensure_internet(config, try_wifi=False):
    """Check internet. In live ISO (try_wifi=True), attempt WiFi if not connected."""
    if check_internet():
        logger.info("Internet: connected")
        return

    logger.warning("Internet: not connected")

    if try_wifi:
        logger.info("Attempting WiFi connection via iwctl")
        if connect_wifi(config):
            logger.info("WiFi connected")
            return
        raise RuntimeError("WiFi connection failed — check network.wifi in config")

    raise RuntimeError("No internet connection")

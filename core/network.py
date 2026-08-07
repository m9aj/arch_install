# core/network.py

import shlex
import time
from core.shell import run
from core.logger import logger


def check_internet():
    result = run("ping -c 1 -W 3 google.com", check=False)
    return result.returncode == 0


def detect_wifi_interface():
    result = run("iwctl device list", check=False)
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts and parts[0].startswith("wlan"):
            return parts[0]
    return "wlan0"


def connect_wifi(config):
    wifi = config.get("network", {}).get("wifi", {})
    ssid = wifi.get("ssid")
    password = wifi.get("password")

    if not ssid:
        logger.warning("No WiFi SSID configured in network.wifi")
        return False

    interface = wifi.get("interface") or detect_wifi_interface()
    logger.info(f"Connecting to WiFi: {ssid} on {interface}")

    if password:
        result = run(f"iwctl --passphrase {shlex.quote(password)} station {shlex.quote(interface)} connect {shlex.quote(ssid)}", check=False)
    else:
        result = run(f"iwctl station {shlex.quote(interface)} connect {shlex.quote(ssid)}", check=False)

    if result.returncode != 0:
        return False

    logger.info("Waiting for connection...")
    time.sleep(4)
    return check_internet()



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

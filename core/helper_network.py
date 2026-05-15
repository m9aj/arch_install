# core/network.py

import shlex
import time
from core.helper_basic import run
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


def apply_static_hosts(config):
    hosts = config.get("network", {}).get("hosts", {})
    if not hosts:
        return False
    for hostname, ip in hosts.items():
        check = run(f"grep -q '[[:space:]]{hostname}' /etc/hosts", check=False)
        if check.returncode == 0:
            run(f"sudo sed -i '/[[:space:]]{hostname}$/s/^.*/{ip}  {hostname}/' /etc/hosts")
        else:
            run(f"echo '{ip}  {hostname}' | sudo tee -a /etc/hosts > /dev/null")
        logger.info(f"[network] /etc/hosts: {ip}  {hostname}")
    return True


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

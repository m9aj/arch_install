# postreboot/config_steps.py
# Post-reboot config steps that don't belong to a feature.

import os
import re
import shutil
from core.shell import run
from core.logger import logger


def configure_citrix(config):
    user = config["system"]["username"]
    home = f"/home/{user}"
    src = "/opt/Citrix/ICAClient/config"

    if not os.path.exists(src):
        return False  # icaclient not installed on this machine

    logger.info("Configuring Citrix")
    
    # Ensure .ICAClient exists
    ica_dir = f"{home}/.ICAClient"
    os.makedirs(f"{ica_dir}/cache", exist_ok=True)
    
    # Copy configuration files safely
    ini_files = ["All_Regions.ini", "Trusted_Region.ini", "Unknown_Region.ini", "canonicalization.ini", "regions.ini"]
    for fname in ini_files:
        src_path = os.path.join(src, fname)
        if os.path.exists(src_path):
            shutil.copy(src_path, os.path.join(ica_dir, fname))


def apply_static_hosts(config):
    hosts = config.get("network", {}).get("hosts", {})
    if not hosts:
        return False

    res = run("cat /etc/hosts", check=False)
    content = res.stdout if res.returncode == 0 else ""

    for hostname, ip in hosts.items():
        pattern = rf'^[ \t]*[0-9a-fA-F:.]+[ \t]+{re.escape(hostname)}(?=[ \t]|$)'
        replacement = f"{ip}  {hostname}"
        if re.search(pattern, content, flags=re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        else:
            content = content.rstrip("\n") + f"\n{replacement}\n"
        logger.info(f"[network] /etc/hosts: {ip}  {hostname}")

    run("sudo tee /etc/hosts > /dev/null", input_data=content, log_cmd=False)
    return True

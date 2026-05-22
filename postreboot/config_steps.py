# postreboot/config_steps.py
# Post-reboot config steps that don't belong to a feature.

import os
import pwd
from core.helper_basic import run
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
    run(f"mkdir -p {ica_dir}/cache")
    
    # Copy files
    run(f"cp {src}/{{All_Regions,Trusted_Region,Unknown_Region,canonicalization,regions}}.ini {ica_dir}/")


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

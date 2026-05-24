# features/pia.py
# Configures Private Internet Access VPN via NetworkManager OpenVPN.
# Phase: postboot (after first reboot).

import sys
import os
import re
import shlex
import shutil
import tempfile
import urllib.request
import uuid
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_basic import run
from core.logger import logger

PACMAN_PACKAGES = ["networkmanager-openvpn", "curl"]
AUR_PACKAGES = []
SERVICES = []

NM_TEMPLATE = """[connection]
id=##id##
uuid=##uuid##
type=vpn

[vpn]
service-type=org.freedesktop.NetworkManager.openvpn
connection-type=password
password-flags=0
remote=##remote##
comp-lzo=yes
reneg-seconds=0
port=1198
username=##username##
remote-cert-tls=server
ca=/etc/openvpn/client/ca.rsa.2048.crt
dev=tun
proto-tcp=no
cipher=AES-128-CBC
auth=SHA1

[ipv6]
method=auto

[ipv4]
method=auto

[vpn-secrets]
password=##password##
"""


def clean_name(name):
    """Title-cases names and upper-cases two-letter words (e.g. US, UK, AU)."""
    name = name.replace('_', ' ')
    words = []
    for w in name.split():
        if not w:
            continue
        w_cap = w[0].upper() + w[1:].lower() if len(w) > 0 else ''
        if len(w_cap) == 2 and w_cap.isalpha():
            w_cap = w_cap.upper()
        words.append(w_cap)
    return ' '.join(words)


def download_file(url, dest_path):
    """Downloads a file from a URL using urllib, using a browser User-Agent."""
    logger.info(f"[pia] Downloading {url}...")
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        return True
    except Exception as e:
        logger.error(f"[pia] Failed to download {url}: {e}")
        return False


def configure(config, feature):
    cfg = feature.get("config", {})

    username = cfg.get("username")
    password = cfg.get("password")

    if not username or not password:
        logger.warning("[pia] Missing username or password in config, skipping")
        return False

    hosts = cfg.get("hosts", "")

    # Convert hosts configuration to list
    if isinstance(hosts, str):
        hosts_list = [h.strip() for h in hosts.split(",") if h.strip()]
    elif isinstance(hosts, list):
        hosts_list = [h.strip() for h in hosts if h.strip()]
    else:
        hosts_list = []

    # Local staging directories under temp_dir (user-writable)
    temp_dir = tempfile.mkdtemp(prefix="pia-setup-")
    stage_client_dir = os.path.join(temp_dir, "openvpn-client")
    stage_nm_dir = os.path.join(temp_dir, "nm-connections")
    os.makedirs(stage_client_dir, exist_ok=True)
    os.makedirs(stage_nm_dir, exist_ok=True)

    hosts_dict = {}

    try:
        # Download standard configs (contains ca.rsa.2048.crt and hosts mapping)
        url = 'https://www.privateinternetaccess.com/openvpn/openvpn.zip'
        zip_path = os.path.join(temp_dir, "openvpn.zip")
        
        if not download_file(url, zip_path):
            logger.error("[pia] Failed to acquire openvpn.zip archive. Aborting setup.")
            return False
            
        logger.info("[pia] Extracting certificates and configurations...")
        with zipfile.ZipFile(zip_path, 'r') as z:
            for name in z.namelist():
                basename = os.path.basename(name)
                # Only extract 2048-bit keys since we only configure port 1198 (default)
                if basename in ['ca.rsa.2048.crt', 'crl.rsa.2048.pem']:
                    dest = os.path.join(stage_client_dir, basename)
                    with open(dest, 'wb') as f:
                        f.write(z.read(name))
                elif name.endswith('.ovpn'):
                    content = z.read(name).decode('utf-8', errors='ignore')
                    remote_match = re.search(r'^\s*remote\s+([^\s]+)', content, re.MULTILINE)
                    if remote_match:
                        fqdn = remote_match.group(1).strip()
                        if basename.endswith('.ovpn'):
                            basename = basename[:-5]
                        display_name = clean_name(basename)
                        hosts_dict[display_name] = fqdn

        # Filter the regions to configure
        valid_hosts = []
        if hosts_list:
            for host in hosts_list:
                found_match = None
                # Check exact case-insensitive match
                for key in hosts_dict.keys():
                    if key.lower() == host.lower():
                        found_match = key
                        break
                # Check partial substring match if no exact match
                if not found_match:
                    for key in hosts_dict.keys():
                        if host.lower() in key.lower():
                            found_match = key
                            break
                if found_match:
                    valid_hosts.append(found_match)
                else:
                    logger.warning(f"[pia] Host '{host}' is not recognized. Skipping.")
        else:
            valid_hosts = list(hosts_dict.keys())

        if not valid_hosts:
            logger.error("[pia] No valid hosts found to configure.")
            return False

        # Generate NetworkManager connection profiles in staging directory
        for host_name in valid_hosts:
            fqdn = hosts_dict[host_name]
            safe_name = host_name.replace(' ', '_')
            
            logger.info(f"[pia] Staging profile for '{host_name}'...")
            nm_conf_file = os.path.join(stage_nm_dir, safe_name)
            
            # Format connection template
            content = NM_TEMPLATE.replace('##id##', host_name)
            content = content.replace('##uuid##', str(uuid.uuid4()))
            content = content.replace('##remote##', fqdn)
            content = content.replace('##username##', username)
            content = content.replace('##password##', password)
            
            try:
                with open(nm_conf_file, 'w') as f:
                    f.write(content)
            except OSError as e:
                logger.error(f"[pia] Failed to write staging NetworkManager config: {e}")

        # Deploy staged configurations to system directories using sudo commands
        logger.info("[pia] Installing certificates via sudo...")
        run("sudo mkdir -p /etc/openvpn/client", check=False)
        
        client_files = os.listdir(stage_client_dir)
        if client_files:
            run(f"sudo cp -f {shlex.quote(stage_client_dir)}/* /etc/openvpn/client/", check=False)
            for f in client_files:
                target_path = os.path.join("/etc/openvpn/client", f)
                run(f"sudo chmod 600 {shlex.quote(target_path)}", check=False)
                run(f"sudo chown root:root {shlex.quote(target_path)}", check=False)

        logger.info("[pia] Installing NetworkManager connections via sudo...")
        run("sudo mkdir -p /etc/NetworkManager/system-connections", check=False)
        
        nm_files = os.listdir(stage_nm_dir)
        if nm_files:
            run(f"sudo cp -f {shlex.quote(stage_nm_dir)}/* /etc/NetworkManager/system-connections/", check=False)
            for f in nm_files:
                target_path = os.path.join("/etc/NetworkManager/system-connections", f)
                run(f"sudo chmod 600 {shlex.quote(target_path)}", check=False)
                run(f"sudo chown root:root {shlex.quote(target_path)}", check=False)

            logger.info("[pia] Reloading NetworkManager connections...")
            run("sudo nmcli connection reload", check=False)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    logger.info("[pia] Private Internet Access VPN configuration complete")
    return True

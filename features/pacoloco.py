# features/pacoloco.py
# Pacoloco — caching proxy for official Arch Linux packages.
# Runs its own HTTP server (no nginx needed); clients point pacman at it directly.
#
# Server role: installs pacoloco, writes /etc/pacoloco.yaml, enables the service.
# Client role (configure_client): writes /etc/pacman.d/pacoloco-mirrorlist and
#   injects it before the main mirrorlist in pacman.conf so official packages are
#   fetched via the local cache when the server is reachable.
#
# Called as an early STEP in postreboot/main.py (before aur_packages) so pacman
# already has the pacoloco mirror available when packages are installed.

import os
import socket
import sys
import tempfile
from urllib.parse import urlparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_basic import run
from core.logger import logger


def _is_reachable(url, timeout=3):
    parsed = urlparse(url)
    host   = parsed.hostname
    port   = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

AUR_PACKAGES = ["pacoloco"]

_PACOLOCO_CONF = """\
port: {port}
cache_dir: {cache_dir}
repos:
  archlinux:
    urls:
{urls}"""


def _read_mirrorlist(limit=5):
    mirrors = []
    try:
        with open("/etc/pacman.d/mirrorlist") as f:
            for line in f:
                line = line.strip()
                if line.startswith("Server = "):
                    base = line[len("Server = "):].split("/$repo")[0]
                    if base not in mirrors:
                        mirrors.append(base)
                    if len(mirrors) >= limit:
                        break
    except FileNotFoundError:
        pass
    return mirrors or [
        "https://mirror.rackspace.com/archlinux",
        "https://mirrors.kernel.org/archlinux",
    ]


def _configure_pacoloco(port, cache_dir, mirrors):
    urls = "".join(f"      - {m}\n" for m in mirrors)
    conf = _PACOLOCO_CONF.format(port=port, cache_dir=cache_dir, urls=urls)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(conf)
        tmp = f.name
    run(f"sudo cp {tmp} /etc/pacoloco.yaml")
    run(f"rm {tmp}")


def configure(config, feature):
    cfg       = feature.get("server", {}).get("config", {})
    port      = cfg.get("port",      9129)
    cache_dir = cfg.get("cache_dir", "/var/cache/pacoloco")

    _configure_pacoloco(port, cache_dir, _read_mirrorlist())
    run("sudo systemctl enable pacoloco")
    run("sudo systemd-tmpfiles --create /usr/lib/tmpfiles.d/pacoloco.conf")
    run(f"sudo chown -R pacoloco:pacoloco {cache_dir}")
    run("sudo systemctl start pacoloco")
    run(f"sudo firewall-cmd --permanent --add-port={port}/tcp", check=False)
    run("sudo firewall-cmd --reload", check=False)
    logger.info("[pacoloco] Service enabled and running")


def configure_client(config):
    """Configure client to use the server's pacoloco cache. Reads from features.pacoloco.client."""
    feat = config.get("features", {}).get("pacoloco", {})
    if not feat.get("client", {}).get("enabled", False):
        return False
    cfg = feat.get("client", {}).get("config", {})
    url = cfg.get("url")
    if not url:
        return False

    mirrorlist_url = f"{url}/repo/archlinux/$repo/os/$arch"
    mirrorlist     = "/etc/pacman.d/pacoloco-mirrorlist"
    pacman_conf    = "/etc/pacman.conf"

    if _is_reachable(url):
        content = f"Server = {mirrorlist_url}\n"
        logger.info(f"[pacoloco] Server reachable — writing {mirrorlist}")
    else:
        content = "# pacoloco offline\n"
        logger.info(f"[pacoloco] Server unreachable — writing placeholder {mirrorlist}")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
        f.write(content)
        tmp = f.name
    run(f"sudo cp {tmp} {mirrorlist}")
    run(f"sudo chmod 644 {mirrorlist}")
    run(f"rm {tmp}")

    check = run(f"grep -q 'pacoloco-mirrorlist' {pacman_conf}", check=False)
    if check.returncode == 0:
        logger.info("[pacoloco] pacoloco-mirrorlist already in pacman.conf")
    else:
        logger.info(f"[pacoloco] Injecting {mirrorlist} into pacman.conf")
        run(
            f"sudo sed -i "
            f"'s|^Include = /etc/pacman.d/mirrorlist$"
            f"|Include = {mirrorlist}\\nInclude = /etc/pacman.d/mirrorlist|' "
            f"{pacman_conf}"
        )

    return True

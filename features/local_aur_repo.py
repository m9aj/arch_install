# features/local_aur_repo.py
# Builds AUR packages into a local pacman repo served by nginx on port 8080.
#
# Server role: installs nginx, builds AUR packages, serves them at /{name}/.
# A systemd timer (local-aur-repo-update.timer, weekly + Persistent=true) handles
# building and updating packages asynchronously after install.
#
# Client role (configure_client): adds [local-aur-repo] to pacman.conf and installs
# a NetworkManager dispatcher that keeps /etc/hosts in sync as you move between
# home LAN and Tailscale.
#
# Called as an early STEP in postreboot/main.py (before aur_packages).

import os
import shlex
import socket
import sys
import tempfile
from urllib.parse import urlparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.helper_basic import run
from core.logger import logger

PACMAN_PACKAGES = ["nginx", "git", "base-devel"]

_NGINX_CONF = """\
server {{
    listen {port};
    server_name _;

    location /{name}/ {{
        root /srv;
        autoindex on;
    }}
}}
"""

# Update script installed to /usr/local/bin/local-aur-repo-update.
# REPO_DIR and REPO_NAME are substituted at install time.
_UPDATE_SCRIPT = """\
#!/usr/bin/env python3
# Managed by arch-install local_aur_repo feature. Edit /etc/local-aur-repo/packages to
# add or remove packages; this script runs weekly via local-aur-repo-update.timer.

import glob
import json
import os
import re
import subprocess
import sys
import tarfile
import urllib.request

REPO_DIR  = "{repo_dir}"
REPO_NAME = "{repo_name}"
ARCH_DIR  = os.path.join(REPO_DIR, "x86_64")
PKG_LIST  = "/etc/local-aur-repo/packages"
BUILD_DIR = os.path.join(os.path.expanduser("~"), ".cache", "local-aur-repo", "build")
AUR_BASE  = "https://aur.archlinux.org"


def _read_file_lines(path):
    if not os.path.exists(path):
        return []
    items = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            items.append(line)
    return items


_aur_cache = {{}}


def _aur_info(pkg):
    if pkg in _aur_cache:
        return _aur_cache[pkg]
    url = f"{{AUR_BASE}}/rpc/v5/info?arg[]={{pkg}}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read())
        results = data.get("results", [])
        result = results[0] if results else None
    except Exception as e:
        print(f"[local-aur-repo] AUR RPC failed for {{pkg}}: {{e}}", file=sys.stderr)
        result = None
    _aur_cache[pkg] = result
    return result


def _aur_info_batch(pkgs):
    uncached = [p for p in pkgs if p not in _aur_cache]
    if not uncached:
        return
    url = AUR_BASE + "/rpc/v5/info?" + "&".join(f"arg[]={{p}}" for p in uncached)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read())
        for result in data.get("results", []):
            name = result.get("Name")
            if name:
                _aur_cache[name] = result
    except Exception as e:
        print(f"[local-aur-repo] AUR batch RPC failed: {{e}}", file=sys.stderr)
    for p in uncached:
        if p not in _aur_cache:
            _aur_cache[p] = None


def _in_official_repos(pkg):
    # -Sddp resolves via provides so virtual names like 'libgl' or 'atk' that
    # are satisfied by official-repo packages are correctly detected.
    return subprocess.run(
        ["pacman", "-Sddp", pkg], capture_output=True
    ).returncode == 0


def _resolve_build_order(requested):
    # Return all packages in build order, AUR deps before their dependents.
    _aur_info_batch(requested)
    seen   = set()
    order  = []

    def _visit(pkg):
        if pkg in seen:
            return
        seen.add(pkg)
        info = _aur_info(pkg)
        if info:
            all_deps = info.get("Depends", []) + info.get("MakeDepends", [])
            for dep in all_deps:
                dep_name = re.split(r"[><=!]", dep)[0].strip()
                if dep_name not in seen and not _in_official_repos(dep_name):
                    _visit(dep_name)
        order.append(pkg)

    for pkg in requested:
        _visit(pkg)
    return order


def _clone_or_update(pkg):
    pkg_dir = os.path.join(BUILD_DIR, pkg)
    aur_url = f"{{AUR_BASE}}/{{pkg}}.git"
    if os.path.isdir(os.path.join(pkg_dir, ".git")):
        subprocess.run(
            ["git", "-C", pkg_dir, "pull", "--rebase", "--autostash"],
            check=True,
        )
    else:
        os.makedirs(BUILD_DIR, exist_ok=True)
        subprocess.run(["git", "clone", aur_url, pkg_dir], check=True)
    return pkg_dir


def _build_package(pkg):
    if not re.match(r"^[a-zA-Z0-9_@+.-]+$", pkg):
        print(f"[local-aur-repo] Skipping unsafe package name: {{pkg!r}}", file=sys.stderr)
        return False

    info     = _aur_info(pkg)
    existing = sorted(glob.glob(os.path.join(ARCH_DIR, f"{{pkg}}-*.pkg.tar.zst")))

    if info and existing:
        version = info.get("Version", "")
        if any(f"-{{version}}-" in os.path.basename(f) for f in existing):
            print(f"[local-aur-repo] {{pkg}} {{version}} already up-to-date, skipping")
            return True

    try:
        pkg_dir = _clone_or_update(pkg)
    except subprocess.CalledProcessError as e:
        print(f"[local-aur-repo] Failed to fetch {{pkg}} from AUR: {{e}}", file=sys.stderr)
        if existing:
            print(f"[local-aur-repo] Using cached build for {{pkg}}")
            return True
        return False

    if not os.path.exists(os.path.join(pkg_dir, "PKGBUILD")):
        print(f"[local-aur-repo] {{pkg}}: no PKGBUILD in AUR (virtual/provides name), skipping")
        return True

    r = subprocess.run(
        ["makepkg", "-s", "--noconfirm", "--noprogressbar", "--skippgpcheck"],
        cwd=pkg_dir,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip()[-3000:]
        print(f"[local-aur-repo] makepkg failed for {{pkg}}:\\n{{tail}}", file=sys.stderr)
        return False

    built = sorted(glob.glob(os.path.join(pkg_dir, "*.pkg.tar.zst")))
    if not built:
        print(f"[local-aur-repo] No package produced for {{pkg}}", file=sys.stderr)
        return False

    new_pkgs = []
    for pkg_file in built:
        dest = os.path.join(ARCH_DIR, os.path.basename(pkg_file))
        if not os.path.exists(dest):
            subprocess.run(["cp", pkg_file, ARCH_DIR], check=True)
            print(f"[local-aur-repo] Copied: {{os.path.basename(pkg_file)}}")
            new_pkgs.append(dest)
        else:
            print(f"[local-aur-repo] Already up-to-date: {{pkg}}")
    if new_pkgs:
        db = os.path.join(ARCH_DIR, f"{{REPO_NAME}}.db.tar.gz")
        subprocess.run(["repo-add", "-R", db] + new_pkgs, check=True)
        subprocess.run(["sudo", "pacman", "-Sy", REPO_NAME], check=False)
    return True


def _cleanup_unreferenced():
    db_path = os.path.join(ARCH_DIR, f"{{REPO_NAME}}.db.tar.gz")
    if not os.path.exists(db_path):
        return
    referenced = set()
    try:
        with tarfile.open(db_path) as tar:
            for member in tar.getmembers():
                if member.name.endswith("/desc"):
                    fobj = tar.extractfile(member)
                    if fobj:
                        lines = fobj.read().decode().splitlines()
                        for i, line in enumerate(lines):
                            if line == "%FILENAME%" and i + 1 < len(lines):
                                referenced.add(lines[i + 1])
    except Exception as e:
        print(f"[local-aur-repo] Could not read db for cleanup: {{e}}", file=sys.stderr)
        return
    for pkg_file in glob.glob(os.path.join(ARCH_DIR, "*.pkg.tar.zst")):
        if os.path.basename(pkg_file) not in referenced:
            os.remove(pkg_file)
            print(f"[local-aur-repo] Removed old version: {{os.path.basename(pkg_file)}}")


def main():
    os.makedirs(ARCH_DIR, exist_ok=True)

    # Sync all repos so _in_official_repos() sees current package lists and
    # so makepkg -s can install deps from official repos without a separate -Sy.
    subprocess.run(["sudo", "pacman", "-Sy"], check=False)

    requested = _read_file_lines(PKG_LIST)
    if not requested:
        print("[local-aur-repo] No packages listed in " + PKG_LIST)
        return

    build_order = _resolve_build_order(requested)
    extra = [p for p in build_order if p not in requested]
    if extra:
        print(f"[local-aur-repo] AUR deps to build first: {{', '.join(extra)}}")
    print(f"[local-aur-repo] Building {{len(requested)}} package(s): {{', '.join(requested)}}")

    failed = []
    for pkg in build_order:
        if not _build_package(pkg):
            failed.append(pkg)

    pkg_files = glob.glob(os.path.join(ARCH_DIR, "*.pkg.tar.zst"))
    if pkg_files:
        db = os.path.join(ARCH_DIR, f"{{REPO_NAME}}.db.tar.gz")
        subprocess.run(["repo-add", "-R", db] + pkg_files, check=True)
        _cleanup_unreferenced()
    requested_failures = [p for p in failed if p in requested]
    if requested_failures:
        print(f"[local-aur-repo] Failed: {{', '.join(requested_failures)}}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
"""

_SERVICE_UNIT = """\
[Unit]
Description=Local AUR repository update
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User={user}
Environment=MAKEFLAGS=-j{ncpu}
ExecStart=/usr/local/bin/local-aur-repo-update
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

_TIMER_UNIT = """\
[Unit]
Description=Local AUR repository weekly update

[Timer]
OnCalendar=weekly
Persistent=true
RandomizedDelaySec=1h

[Install]
WantedBy=timers.target
"""


def _is_reachable(url, timeout=3):
    parsed = urlparse(url)
    host   = parsed.hostname
    port   = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _set_hosts_entry(hostname, ip):
    check = run(f"grep -q '[[:space:]]{hostname}' /etc/hosts", check=False)
    if check.returncode == 0:
        run(f"sudo sed -i '/[[:space:]]{hostname}$/s/^.*/{ip}  {hostname}/' /etc/hosts")
    else:
        run(f"echo '{ip}  {hostname}' | sudo tee -a /etc/hosts > /dev/null")


def _create_empty_pacman_db(name):
    """Create an empty but valid pacman sync database.

    When [local-aur-repo] is in pacman.conf but its database has never been
    downloaded (e.g. server is offline), every `pacman -S` fails with
    "database file does not exist". A valid empty archive satisfies pacman
    until the next `pacman -Syu` when the server is reachable.
    """
    import tarfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    with tarfile.open(tmp, "w:gz"):
        pass
    run(f"sudo mkdir -p /var/lib/pacman/sync")
    run(f"sudo cp {tmp} /var/lib/pacman/sync/{name}.db")
    run(f"rm {tmp}")
    logger.info(f"[local_aur_repo] Created empty placeholder db for [{name}] — will be replaced when server has packages")


def configure_client(config):
    """Configure client to use the server's local AUR repo. Reads from features.local_aur_repo.client."""
    feat = config.get("features", {}).get("local_aur_repo", {})
    if not feat.get("client", {}).get("enabled", False):
        return False
    cfg = feat.get("client", {}).get("config", {})
    url = cfg.get("url")
    if not url:
        return False

    tailscale_ip = cfg.get("tailscale_ip") or ""
    parsed       = urlparse(url)
    hostname     = parsed.hostname           # aur.local
    name         = parsed.path.strip("/").split("/")[-1] or "local-aur-repo"

    # Pin aur.local → Tailscale IP permanently. Tailscale is always-on so no
    # dynamic host switching is needed — it works on LAN and off LAN alike.
    if tailscale_ip:
        _set_hosts_entry(hostname, tailscale_ip)

    # Add [local-aur-repo] to pacman.conf, or migrate an existing entry whose
    # Server URL still points to the old hostname (media.local).
    check = run(f"grep -q '\\[{name}\\]' /etc/pacman.conf", check=False)
    if check.returncode == 0:
        url_check = run(f"grep -qF 'Server = {url}/$arch' /etc/pacman.conf", check=False)
        if url_check.returncode != 0:
            logger.info(f"[local_aur_repo] Migrating [{name}] Server URL → {url}/$arch")
            run(f"sudo sed -i 's|Server = .*/local-aur-repo/\\$arch|Server = {url}/\\$arch|' /etc/pacman.conf")
        else:
            logger.info(f"[local_aur_repo] [{name}] already in pacman.conf")
    else:
        logger.info(f"[local_aur_repo] Adding [{name}] → {url}/$arch")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(
                f"\n[{name}]\nSigLevel = Optional TrustAll\n"
                f"Usage = All\nServer = {url}/$arch\n"
            )
            tmp = f.name
        run(f"sudo tee -a /etc/pacman.conf < {shlex.quote(tmp)} > /dev/null")
        run(f"rm {shlex.quote(tmp)}")

    if _is_reachable(url):
        result = run("sudo pacman -Sy --noconfirm", check=False)
        if result.returncode != 0:
            logger.warning("[local_aur_repo] pacman -Sy had errors")
    else:
        logger.warning("[local_aur_repo] aur.local unreachable — skipping pacman -Sy (Tailscale up?)")

    if not os.path.exists(f"/var/lib/pacman/sync/{name}.db"):
        _create_empty_pacman_db(name)

    return True


def configure(config, feature):
    cfg      = feature.get("server", {}).get("config", {})
    name     = cfg.get("name",           "local-aur-repo")
    path     = cfg.get("path",           "/srv/local-aur-repo")
    port     = cfg.get("port",           8080)
    extra    = cfg.get("extra_packages", [])
    user     = config["system"]["username"]
    arch_dir = f"{path}/x86_64"

    run(f"sudo mkdir -p {arch_dir}")
    run(f"sudo chown -R {user}:{user} {path}")

    packages = _discover_aur_packages(config)
    packages = list(dict.fromkeys(packages + extra))
    logger.info(f"[local_aur_repo] Discovered packages: {', '.join(packages) or 'none'}")

    _write_package_list(packages)
    _install_update_script(path, name)
    _install_systemd_units(user)

    _configure_makepkg(user)
    _configure_nginx(name, port)
    _add_server_pacman_repo(name, arch_dir)
    run("sudo pacman -Sy --noconfirm", check=False)
    run("sudo systemctl enable --now nginx")
    run(f"sudo firewall-cmd --permanent --add-port={port}/tcp", check=False)
    run("sudo firewall-cmd --reload", check=False)
    run("sudo systemctl enable --now local-aur-repo-update.timer")
    logger.info("[local_aur_repo] Timer enabled — initial build will start shortly")


def _discover_aur_packages(config):
    import yaml
    from core.helper_core import CONFIG_DIR, detect_profile

    current = detect_profile() or ""
    skip = {"base", "package_profiles", current}
    packages = []

    for filename in sorted(os.listdir(CONFIG_DIR)):
        if not filename.endswith(".yaml"):
            continue
        stem = filename[:-5]
        if stem in skip or stem.startswith("secrets"):
            continue
        try:
            with open(os.path.join(CONFIG_DIR, filename)) as f:
                cfg = yaml.safe_load(f) or {}
            pkgs = cfg.get("machine_specific", {}).get("aur", [])
            for p in pkgs:
                if p not in packages:
                    packages.append(p)
        except Exception as e:
            logger.warning(f"[local_aur_repo] Could not read {filename}: {e}")

    return packages


def _write_package_list(packages):
    lines = [
        "# /etc/local-aur-repo/packages",
        "# One package name per line. Lines starting with # are ignored.",
        "# Auto-populated from machine profile YAMLs (machine_specific.aur).",
        "# Add extra packages here at any time — the weekly timer will pick them up.",
        "",
    ] + packages + [""]

    content = "\n".join(lines)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(content)
        tmp = f.name

    run("sudo mkdir -p /etc/local-aur-repo")
    run(f"sudo cp {tmp} /etc/local-aur-repo/packages")
    run("sudo chmod 644 /etc/local-aur-repo/packages")
    run(f"rm {tmp}")
    logger.info("[local_aur_repo] Wrote /etc/local-aur-repo/packages")


def _install_update_script(repo_dir, repo_name):
    script = _UPDATE_SCRIPT.format(repo_dir=repo_dir, repo_name=repo_name)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        tmp = f.name

    run(f"sudo cp {tmp} /usr/local/bin/local-aur-repo-update")
    run("sudo chmod 755 /usr/local/bin/local-aur-repo-update")
    run(f"rm {tmp}")
    logger.info("[local_aur_repo] Installed /usr/local/bin/local-aur-repo-update")


def _install_systemd_units(user):
    service = _SERVICE_UNIT.format(user=user, ncpu=os.cpu_count() or 4)
    timer   = _TIMER_UNIT

    for unit_name, content in [
        ("local-aur-repo-update.service", service),
        ("local-aur-repo-update.timer",   timer),
    ]:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(content)
            tmp = f.name
        run(f"sudo cp {tmp} /etc/systemd/system/{unit_name}")
        run(f"rm {tmp}")

    run("sudo systemctl daemon-reload")
    logger.info("[local_aur_repo] Installed systemd service and timer units")
    _install_sudoers_rule(user)


def _install_sudoers_rule(user):
    # makepkg -s calls sudo pacman -S to install deps, and the update script
    # calls sudo pacman -Sy to refresh the db — both run without a TTY in the
    # systemd service context, so a NOPASSWD rule scoped to pacman is required.
    #
    # Rules in /etc/sudoers.d are inserted at the @includedir line. On Arch the
    # %wheel rule sits AFTER @includedir (last-match-wins), so any sudoers.d
    # entry is overridden by the wheel rule requiring a password. Appending
    # directly to /etc/sudoers places the rule after %wheel so it wins.
    marker = f"{user} ALL=(ALL:ALL) NOPASSWD: /usr/bin/pacman"
    check = f"sudo grep -qF '{marker}' /etc/sudoers"
    append = (
        f"sudo bash -c 'echo \"{marker}\" >> /etc/sudoers"
        f" && visudo -c"
        f" || sed -i \"/{user} ALL=(ALL:ALL) NOPASSWD/d\" /etc/sudoers'"
    )
    run(f"{check} || {append}")
    logger.info(f"[local_aur_repo] Ensured NOPASSWD pacman rule for {user} in /etc/sudoers")


def _configure_makepkg(user):
    # /etc/makepkg.conf uses --jobs=N (long form) which cmake rejects for
    # CMAKE_BUILD_PARALLEL_LEVEL. The user config is sourced last, so it wins.
    run(
        f"sudo -u {user} sh -c "
        f"'mkdir -p ~/.config/pacman"
        f" && echo \"MAKEFLAGS=\\\"-j\\$(nproc)\\\"\" > ~/.config/pacman/makepkg.conf'",
    )
    logger.info(f"[local_aur_repo] Configured user makepkg.conf for {user}")


def _add_server_pacman_repo(name, arch_dir):
    run(
        f"sudo grep -q '\\[{name}\\]' /etc/pacman.conf"
        f" || printf '\\n[{name}]\\nSigLevel = Optional TrustAll\\nServer = file://{arch_dir}\\n'"
        f" | sudo tee -a /etc/pacman.conf > /dev/null"
    )
    db = f"{arch_dir}/{name}.db.tar.gz"
    run(f"test -f {db} || repo-add {db}")
    run(f"ln -sf {name}.db.tar.gz {arch_dir}/{name}.db")
    run(f"ln -sf {name}.files.tar.gz {arch_dir}/{name}.files")
    logger.info(f"[local_aur_repo] Added [{name}] to /etc/pacman.conf")


def _configure_nginx(name, port):
    conf = _NGINX_CONF.format(name=name, port=port)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
        f.write(conf)
        tmp = f.name
    run("sudo mkdir -p /etc/nginx/conf.d")
    run(f"sudo cp {tmp} /etc/nginx/conf.d/{name}.conf")
    run(f"rm {tmp}")
    run(f"sudo sed -i '/listen.*80;/s/^/#/' /etc/nginx/nginx.conf", check=False)
    # Arch's default nginx.conf does not include conf.d/ — add the directive if missing.
    run(
        "sudo grep -q 'include /etc/nginx/conf.d' /etc/nginx/nginx.conf"
        " || sudo sed -i '/^http {/a\\    include /etc/nginx/conf.d/*.conf;' /etc/nginx/nginx.conf",
        check=False,
    )

# preinstall/archinstall.py

from core.helper_basic import run, chroot
from core.helper_disk import get_partition
from core.resolver import resolve_system
from core.logger import logger
import os
import re

# ------------------------
# Pacstrap Core
# ------------------------

def install_core(config):
    logger.info("Running pacstrap")
    system = resolve_system(config)
    core_pkgs = system.get("core", [])
    run(f"pacstrap -K /mnt {' '.join(core_pkgs)} --overwrite '*'")

# ------------------------
# Generate Fstab
# ------------------------

def generate_fstab(config):
    logger.info("Generating fstab")
    run("mkdir -p /mnt/etc")
    run("genfstab -U /mnt > /mnt/etc/fstab")
    # Append custom mounts
    add_custom_fstab_entries(config)

def add_custom_fstab_entries(config):
    fstab_path = "/mnt/etc/fstab"
    disk_cfg = config.get("disk", {})
    
    # Additional Disks
    mounts = config.get("additional_mounts", [])
    if mounts:
        run(f"echo '' >> {fstab_path}")
        run(f"echo '# Additional Disks' >> {fstab_path}")

        type_map = {
            "ssd": "mount_ops_ssd",
            "hdd": "mount_ops_hdd"
        }

        for m in mounts:
            base = m.get("disk_by_id")
            if not base: continue
            
            device = get_partition(base, m.get("part"))
            mountpoint = m["mountpoint"]
            disk_type = m.get("type", "ssd")
            
            # Resolve UUID for the device
            uuid_res = run(f"blkid -s UUID -o value {device}", check=False)
            if uuid_res.returncode == 0 and uuid_res.stdout.strip():
                dev_spec = f"UUID={uuid_res.stdout.strip()}"
            else:
                logger.warning(f"Could not resolve UUID for {device}, falling back to path")
                dev_spec = device
            
            key = type_map.get(disk_type, "mount_ops_ssd")
            type_opts = disk_cfg.get(key, "")
            other_opts = disk_cfg.get("mount_ops_oth", "")
            opts = ",".join(o for o in [type_opts, other_opts] if o) or "defaults"

            # Create mount point in /mnt
            run(f"mkdir -p /mnt{mountpoint}")
            run(f"echo '{dev_spec}  {mountpoint}  btrfs  {opts}  0 2' >> {fstab_path}")

    # Bind Mounts
    binds = config.get("bind_mounts", [])
    if binds:
        run(f"echo '' >> {fstab_path}")
        run(f"echo '# Bind Mounts' >> {fstab_path}")
        for b in binds:
            src = b["source"]
            tgt = b["target"]
            # Create target mount point in /mnt
            run(f"mkdir -p /mnt{tgt}")
            run(f"echo '{src}  {tgt}  none  bind  0 0' >> {fstab_path}")

# ------------------------
# Config System
# ------------------------

def set_hostname(config):
    hostname = config["system"]["hostname"]
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$', hostname):
        raise ValueError(f"Invalid hostname: {hostname!r}")
    chroot(f"echo {hostname} > /etc/hostname")

def set_timezone(config):
    tz = config["system"]["timezone"]
    if not re.match(r'^[A-Za-z0-9_/+-]+$', tz) or not os.path.exists(f"/usr/share/zoneinfo/{tz}"):
        raise ValueError(f"Invalid or unknown timezone: {tz!r}")
    chroot(f"ln -sf /usr/share/zoneinfo/{tz} /etc/localtime")
    chroot("hwclock --systohc")
    chroot("timedatectl set-ntp true")
    chroot("systemctl enable systemd-timesyncd")

def configure_locales():
    chroot("sed -i 's/#\\(en_US.UTF-8\\)/\\1/' /etc/locale.gen")
    chroot("locale-gen")
    chroot("echo LANG=en_US.UTF-8 > /etc/locale.conf")
    chroot("echo KEYMAP=us > /etc/vconsole.conf")

def create_user(config):
    user = config["system"]["username"]
    fullname = config["system"].get("fullname", user)
    chroot(f"id -u {user} >/dev/null 2>&1 || useradd -m -s /bin/zsh -c '{fullname}' {user}")
    chroot(f"usermod -aG wheel {user}")
    # Uncomment the standard %wheel rule if commented out, otherwise append it
    chroot("sed -i 's/^# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/' /etc/sudoers")
    chroot("grep -q '^%wheel ALL=(ALL:ALL) ALL' /etc/sudoers || echo '%wheel ALL=(ALL:ALL) ALL' >> /etc/sudoers")

def set_passwords(config):
    root_pw = config["system"].get("root_password")
    user = config["system"]["username"]
    user_pw = config["system"].get("user_password")

    if root_pw:
        chroot(f"echo 'root:{root_pw}' | chpasswd")
    if user_pw:
        chroot(f"echo '{user}:{user_pw}' | chpasswd")

def configure_autologin(config):
    if not config["system"].get("autologin"):
        return

    de = config["arch"].get("de", "gnome")
    user = config["system"]["username"]

    # Only implement for GNOME/GDM as requested
    if de == "gnome":
        logger.info(f"Enabling GDM autologin for {user}")
        conf_path = "/etc/gdm/custom.conf"
        # The script ensures [daemon] section exists and adds autologin lines.
        # It handles cases where the file might not exist yet by creating it.
        script = f"""
mkdir -p /etc/gdm
if [ ! -f {conf_path} ]; then
  echo -e "[daemon]\\nAutomaticLoginEnable=True\\nAutomaticLogin={user}" > {conf_path}
else
  sed -i '/^AutomaticLoginEnable/d' {conf_path}
  sed -i '/^AutomaticLogin/d' {conf_path}
  if grep -q "\\[daemon\\]" {conf_path}; then
    sed -i '/\\[daemon\\]/a AutomaticLoginEnable=True\\nAutomaticLogin={user}' {conf_path}
  else
    echo -e "\\n[daemon]\\nAutomaticLoginEnable=True\\nAutomaticLogin={user}" >> {conf_path}
  fi
fi
"""
        chroot(script)

def initial_config(config):
    logger.info("Configuring system (chroot)")
    set_hostname(config)
    set_timezone(config)
    configure_locales()
    create_user(config)
    set_passwords(config)
    configure_autologin(config)

# ------------------------
# Tweaks
# ------------------------

def makepkg_block():
    return r"""
# makepkg (parallel builds)
if grep -q "^#MAKEFLAGS=" /etc/makepkg.conf; then
  sed -i "s/^#MAKEFLAGS=.*/MAKEFLAGS=\"-j\$(nproc)\"/" /etc/makepkg.conf
elif grep -q "^MAKEFLAGS=" /etc/makepkg.conf; then
  sed -i "s/^MAKEFLAGS=.*/MAKEFLAGS=\"-j\$(nproc)\"/" /etc/makepkg.conf
else
  echo "MAKEFLAGS=\"-j\$(nproc)\"" >> /etc/makepkg.conf
fi
"""


def pacman_block():
    return r"""
# pacman color
sed -i "s/^#Color/Color/" /etc/pacman.conf
"""

def sysctl_block():
    return r"""
# Network performance improvements
mkdir -p /etc/sysctl.d
printf '%s\n' \
  'net.core.default_qdisc=fq' \
  'net.ipv4.tcp_congestion_control=bbr' \
  'net.core.rmem_max=16777216' \
  'net.core.wmem_max=16777216' \
  'net.ipv4.tcp_rmem=4096 87380 16777216' \
  'net.ipv4.tcp_wmem=4096 65536 16777216' \
  'net.core.somaxconn=65535' \
  'net.core.netdev_max_backlog=65535' \
  'net.ipv4.tcp_slow_start_after_idle=0' \
  'net.ipv4.tcp_mtu_probing=1' \
  'net.ipv4.tcp_fastopen=3' \
  > /etc/sysctl.d/10_network_improvements.conf
"""


def initial_tweaks(config):
    script = "\n".join([
        "set -e",
        makepkg_block(),
        pacman_block(),
        sysctl_block(),
    ])
    chroot(script)

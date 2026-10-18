in ---
name: media-server-pilot
description: >
  Manage, add, remove, and troubleshoot self-hosted services and containerized projects on the
  home media server. Use this skill when managing server containers, Podman quadlets,
  media.local, media.remote, ~/Arch/server, or ~/Arch/projects via SSH.
---

# Media Server Pilot Skill

This skill guides the AI assistant in managing Podman quadlet services, custom container projects,
and infrastructure scripts on the home media server (`media.local` / `media.remote`) over SSH.

---

## 1. Remote Environment & Connection

All interactions with the server occur over SSH from the client machine:

- **LAN Host:** `media.local` (resolved to `192.168.40.100`)
- **Remote / Off-LAN Host:** `media.remote` (`100.100.1.1` via Tailscale)
- **User:** `ajay`
- **Root Directory:** `~/Arch` (symlinked to `/mnt/Personal/_Ajay/Arch`)
  - **Infrastructure Stack:** `~/Arch/server` (Git repo for Podman quadlets stack)
  - **Custom Projects:** `~/Arch/projects/<project_name>` (Individual app repos/code)
  - **Storage Volumes:**
    - App Data: `/mnt/containers/data`
    - Cloud Sync: `/mnt/containers/cloud`
    - Media Drives: `/mnt/containers/media` (`Movies`, `Series`, etc.)

---

## 2. Server Infrastructure Overview (`~/Arch/server`)

The server uses **Podman systemd quadlets** managed by a central python installer (`./install`):

```text
~/Arch/server/
├── assets/
│   ├── quadlets/         # User-level quadlets (*.container, *.volume, *.network)
│   ├── quadlets_root/    # Root-level quadlets (e.g. system services)
│   └── hooks/            # Pre/post deploy scripts (<service>.<pre|post>.py)
├── config/
│   ├── config.yaml       # Master enable/disable toggles and global mount paths
│   ├── secrets.yaml      # Container secret values (synced to podman secret store)
│   └── services/         # Optional service-specific config overrides
├── helpers/
│   ├── install.py        # Quadlet deployment, firewall opening, secret sync
│   └── update.py         # Image pull and container update logic
├── install               # CLI entrypoint: ./install or ./install <service>
└── update                # CLI entrypoint: ./update
```

---

## 3. Workflow: Adding or Deploying a Service

### Step 1: Create the Quadlet Container File
Create the `.container` file under `assets/quadlets/<service_name>.container` on the server:
```ini
[Unit]
Description=<Service Name> Container
After=network-online.target

[Container]
ContainerName=<service_name>
Image=<image_name>:<tag>
PublishPort=<host_port>:<container_port>
Volume=/mnt/containers/data/<service_name>:/config:Z
AutoUpdate=registry
Network=containers.network

[Service]
Restart=always

[Install]
WantedBy=default.target
```

*Note on remote creation:* Use an SSH heredoc to write the file remotely:
```bash
ssh media.local "cat << 'EOF' > ~/Arch/server/assets/quadlets/<service_name>.container
[Unit]
...
EOF"
```

### Step 2: Register in `config/config.yaml`
Add or enable the service in `~/Arch/server/config/config.yaml`:
```yaml
services:
  <service_name>: { enabled: true }
```

### Step 3: Run the Installer
Run the service installer over SSH:
```bash
ssh media.local "cd ~/Arch/server && ./install <service_name>"
```
The installer automatically:
1. Copies the quadlet to `~/.config/containers/systemd/`
2. Syncs secrets if required
3. Opens firewall ports via `firewall-cmd` based on `PublishPort`
4. Runs `systemctl --user daemon-reload` and starts `<service_name>.service`

### Step 4: Verify Service Health
```bash
ssh media.local "systemctl --user status <service_name> --no-pager"
ssh media.local "podman ps | grep <service_name>"
```

---

## 4. Workflow: Removing or Disabling a Service

### Step 1: Disable in Configuration
Edit `~/Arch/server/config/config.yaml` to set `enabled: false`:
```yaml
services:
  <service_name>: { enabled: false }
```

### Step 2: Stop and Mask the Systemd Service
```bash
ssh media.local "systemctl --user stop <service_name>.service"
ssh media.local "systemctl --user disable <service_name>.service"
```

### Step 3: Remove Quadlet Links and Reload
```bash
ssh media.local "rm -f ~/.config/containers/systemd/<service_name>.*"
ssh media.local "systemctl --user daemon-reload"
```

---

## 5. Workflow: Managing Custom Projects (`~/Arch/projects`)

Projects in `~/Arch/projects/` (e.g. `census_calc`, `gemma_chat`, `medical_records`, `resident_schedule`) contain custom code and `Containerfile`s.

1. **Inspect / Edit Project Code:**
   Access the project directory over SSH:
   ```bash
   ssh media.local "cd ~/Arch/projects/<project_name> && git status"
   ```
2. **Build Local Container Image:**
   ```bash
   ssh media.local "cd ~/Arch/projects/<project_name> && podman build -t localhost/<project_name>:latest ."
   ```
3. **Connect to Quadlet:**
   Ensure `assets/quadlets/<project_name>.container` references `Image=localhost/<project_name>:latest`.
4. **Deploy:**
   ```bash
   ssh media.local "cd ~/Arch/server && ./install <project_name>"
   ```

---

## 6. Inspection & Debugging Reference

| Task | Remote Command |
| :--- | :--- |
| **List Running Containers** | `ssh media.local "podman ps"` |
| **Inspect Service Logs** | `ssh media.local "journalctl --user -u <service> -n 100 --no-pager"` |
| **Inspect Container Logs** | `ssh media.local "podman logs --tail 50 <service>"` |
| **Restart Service** | `ssh media.local "systemctl --user restart <service>"` |
| **Check Firewall Ports** | `ssh media.local "sudo firewall-cmd --list-ports"` |
| **Check Disk Storage** | `ssh media.local "df -h /mnt/containers /mnt/Personal"` |

---
description: Deploy Docker Compose application from Windows to remote Raspberry Pi (via SCP/SSH)
---

# Remote Docker Deploy (Windows -> Pi)

Deploys a local project to a remote Raspberry Pi by copying source files via SCP and rebuilding/restarting Docker containers via SSH. Optimized for Windows environments using PowerShell.

## Prerequisites

- **SSH Access**: Key-based authentication to the remote Pi.
- **PowerShell**: Used for local execution.
- **Docker Compose**: Installed on the remote Pi.

## Workflow

1. **Set UTF-8 Encoding**: Ensure PowerShell uses UTF-8 to prevent character encoding issues with filenames or content.
2. **Transfer Files (SCP)**: Copy source code to the remote directory. Use `-r` for recursive directory copy.
3. **Remote Rebuild (SSH)**: Execute `docker compose` commands on the remote server.

## Example Command (PowerShell)

```powershell
# 1. Set Encoding (Crucial for Japanese environments)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 2. Transfer Files
# Replace 'user@192.168.1.100' and paths with your specific configuration
scp -r ./raspberry_pi/* user@192.168.1.100:~/project-name/

# 3. Remote Rebuild & Restart
# - `build --no-cache`: Ensures dependencies are updated
# - `up -d`: Recreates containers in detached mode
ssh user@192.168.1.100 "cd ~/project-name && docker compose build --no-cache && docker compose up -d"
```

## Tips

- **Relative Paths**: Run commands from the project root for consistent paths.
- **Logs**: To check status immediately after deploy:
  ```powershell
  ssh user@192.168.x.x "cd ~/project-name && docker compose logs -f --tail=50"
  ```
- **Network Mode**: If container needs direct hardware access (mDNS, etc.), consider `network_mode: host` in `docker-compose.yml`.

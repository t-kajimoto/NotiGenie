# Raspberry Pi Connection Script

# Configuration
param(
    [string]$TargetHost = "172.16.64.50"  # Fixed IP for Raspberry Pi
)

$PI_USER = "takumomo"
$PI_HOST = $TargetHost

# Check if SSH key exists, if not generate one (optional, but good for first run setup helper)
$SSH_KEY_PATH = "$HOME\.ssh\id_rsa"
if (-not (Test-Path "$SSH_KEY_PATH")) {
    Write-Host "Generating SSH key for password-less login..."
    ssh-keygen -t rsa -b 4096 -f $SSH_KEY_PATH -N ""
    Write-Host "Key generated. You may need to copy it to the Pi manually once if not set up via Imager."
    Write-Host "To copy: Get-Content $SSH_KEY_PATH.pub | ssh $PI_USER@$PI_HOST 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys'"
}

# Connect
Write-Host "Connecting to $PI_USER@$PI_HOST..."
ssh $PI_USER@$PI_HOST

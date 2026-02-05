# Fetch Raspberry Pi Logs Script

# Configuration
param(
    [string]$TargetHost = "172.16.64.50"
)

$PI_USER = "takumomo"
$PI_HOST = $TargetHost
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"
$LOG_DIR = "logs"
$LOG_FILE = "$LOG_DIR\pi_client_$TIMESTAMP.log"

# Create logs directory if it doesn't exist
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR | Out-Null
    Write-Host "Created logs directory: $LOG_DIR"
}

Write-Host "Fetching logs from $PI_USER@$PI_HOST..."
Write-Host "Saving to $LOG_FILE..."

# Execute command remotely and save to file
# We use -f to follow if user wanted, but for snapshot we usually drop -f.
# User asked for "logs review" which might mean snapshot. 
# "タイムスタンプを付けて保存する" implies a snapshot of current logs.
# If "realtime", we can't easily save to file with timestamp and exit.
# I will fetch the last 2000 lines to be safe.

ssh $PI_USER@$PI_HOST "cd ~/notigenie-client && docker compose logs --tail=2000 client" > $LOG_FILE

Write-Host "Done! Log saved to $LOG_FILE"
# Optional: Open the file immediately? Maybe just show path.
Write-Host "You can view it with: Get-Content $LOG_FILE"

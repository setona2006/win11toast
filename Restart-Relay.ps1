# Reload token from .env and restart UCAR relay (same console)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path .env)) {
  Write-Host "ERROR: .env not found in current directory."; exit 1
}

# Read values from .env (robust)
$pushLine   = ((Get-Content -Raw .env) -split '\r?\n' | Where-Object { $_ -match '^PUSH_TOKEN=' } | Select-Object -First 1)
$allowLine  = ((Get-Content -Raw .env) -split '\r?\n' | Where-Object { $_ -match '^ALLOW_CLIENTS=' } | Select-Object -First 1)
$env:PUSH_TOKEN    = ($pushLine  -split '=', 2)[1].Trim().Trim('"')
$env:ALLOW_CLIENTS = ($allowLine -split '=', 2)[1].Trim().Trim('"')

Write-Host "Relay env -> PUSH_TOKEN set, ALLOW_CLIENTS=$env:ALLOW_CLIENTS"

# Stop existing relay on port 8787
$rp = (Get-NetTCPConnection -LocalPort 8787 -ErrorAction SilentlyContinue).OwningProcess
if ($rp) { Stop-Process -Id $rp -Force; Write-Host "Stopped relay PID $rp" } else { Write-Host "No relay on 8787" }

# Start relay (foreground)
uvicorn relay_server:app --host 127.0.0.1 --port 8787



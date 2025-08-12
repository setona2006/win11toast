# Restart UCAR listener with new token (separate console)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path .env)) {
  Write-Host "ERROR: .env not found in current directory."; exit 1
}

$pushLine = ((Get-Content -Raw .env) -split '\r?\n' | Where-Object { $_ -match '^PUSH_TOKEN=' } | Select-Object -First 1)
$token    = ($pushLine -split '=', 2)[1].Trim().Trim('"')

$env:UCAR_WSS        = 'ws://127.0.0.1:8787/alerts'
$env:PUSH_TOKEN      = $token
$env:UCAR_PUSH_TOKEN = $token
$env:UCAR_CLIENT_ID  = 'minato-pc-01'
$env:CLIENT_ID       = $env:UCAR_CLIENT_ID

# Stop existing listener on port 8789
$lp = (Get-NetTCPConnection -LocalPort 8789 -ErrorAction SilentlyContinue).OwningProcess
if ($lp) { Stop-Process -Id $lp -Force; Write-Host "Stopped listener PID $lp" } else { Write-Host "No listener on 8789" }

# Start listener (foreground)
python .\ucar_rt_listener.py



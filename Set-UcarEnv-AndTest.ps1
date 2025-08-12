# ========================
# UCAR .env 更新 & 接続テスト スクリプト
# ========================
param(
    [string]$ClientId = "minato-pc-01",   # デフォルトクライアントID
    [switch]$AddClient,                     # クライアント追加
    [switch]$RemoveClient,                  # クライアント削除
    [string]$RelayHost = "127.0.0.1",     # リレーのホスト名/IP
    [int]$RelayPort = 8787                  # リレーのポート
)

$ErrorActionPreference = 'Stop'

Write-Host "[1/6] 安全な PUSH_TOKEN を生成中..."
# URL安全な Base64 ランダム32バイト
$rng   = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$bytes = New-Object byte[] 32
$rng.GetBytes($bytes)
$token = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')

Write-Host "[2/6] 環境変数へ即時反映 (両互換名)"
$env:PUSH_TOKEN      = $token
$env:UCAR_PUSH_TOKEN = $token
Write-Host "  ✅ PUSH_TOKEN / UCAR_PUSH_TOKEN = $token"

Write-Host "[3/6] .env を更新/作成"
$envPath = Join-Path -Path (Get-Location) -ChildPath ".env"
if (-not (Test-Path $envPath)) {
  "PUSH_TOKEN=$token"      | Set-Content -Path $envPath -Encoding UTF8
  "ALLOW_CLIENTS=$ClientId" | Add-Content -Path $envPath -Encoding UTF8
  Write-Host "  🆕 生成: $envPath"
} else {
  $content    = Get-Content $envPath
  $newContent = @()
  $tokenSet   = $false
  $allowSet   = $false

  foreach ($line in $content) {
    if ($line -match "^PUSH_TOKEN=") {
      $newContent += "PUSH_TOKEN=$token"; $tokenSet = $true
    } elseif ($line -match "^ALLOW_CLIENTS=") {
      $allowSet = $true
      $clients = $line -replace "^ALLOW_CLIENTS=", "" -split ","
      $clients = $clients | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
      if ($AddClient) {
        if ($clients -notcontains $ClientId) { $clients += $ClientId }
      } elseif ($RemoveClient) {
        $clients = $clients | Where-Object { $_ -ne $ClientId }
      } else {
        $clients = @($ClientId)
      }
      $newContent += "ALLOW_CLIENTS=" + ($clients -join ",")
    } else {
      $newContent += $line
    }
  }
  if (-not $tokenSet) { $newContent += "PUSH_TOKEN=$token" }
  if (-not $allowSet) { $newContent += "ALLOW_CLIENTS=$ClientId" }
  $newContent | Set-Content -Path $envPath -Encoding UTF8
  Write-Host "  📝 更新: $envPath"
}

Write-Host "[4/6] 現在の .env 内容:"; Get-Content $envPath | ForEach-Object { "  $_" }

$healthUrl = "http://${RelayHost}:${RelayPort}/health"
Write-Host "[5/6] /health 確認: $healthUrl"
try {
  $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 5
  Write-Host "  /health レスポンス:" ($health | ConvertTo-Json -Depth 4)
} catch {
  Write-Host "  ❌ /health 接続失敗:" $_.Exception.Message
}

Write-Host "[6/6] /push 疎通テスト送信"
$pushUrl = "http://${RelayHost}:${RelayPort}/push"
$ts = [double]([DateTimeOffset]::Now.ToUnixTimeMilliseconds()/1000)
$json = @"
{
  "target": "$ClientId",
  "payload": {
    "ts": $ts,
    "level": "info",
    "message": "【UCAR→直送】疎通テスト",
    "meta": { "symbol": "USDJPY", "price": 148.25 }
  }
}
"@

try {
  $res = Invoke-RestMethod -Method Post -Uri $pushUrl -Headers @{ Authorization = "Bearer $token" } -ContentType 'application/json; charset=utf-8' -Body $json -TimeoutSec 5
  Write-Host "  /push レスポンス:" ($res | ConvertTo-Json -Depth 4)
} catch {
  Write-Host "  ❌ /push 送信失敗:" $_.Exception.Message
  if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message }
}

Write-Host "`nDone. Please confirm toast notification and log append on the listener."



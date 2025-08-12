## UCAR Realtime Alert Listener (Windows 11)

Windows 11 ローカルで動作する最小構成の「アラート受信 → ログ追記 → Windowsトースト表示」ツールです。

- 受信エンドポイント: `http://127.0.0.1:8787/alert`
- フレームワーク: FastAPI
- 通知: `win10toast`

### セットアップ（仮想環境推奨）

PowerShell:

```powershell
py -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### リレー（クラウド/サーバ側）

```powershell
uvicorn relay_server:app --host 0.0.0.0 --port 8787
```
- `.env` を用意（`PUSH_TOKEN` と `ALLOW_CLIENTS`）。サンプル: `.env.example`
- 公開時は HTTPS/WSS 終端（Nginx/Caddy など）推奨

### 起動（環境変数で上書き可能）

どちらでもOKです。

```powershell
# 例: HTTP待受のホスト/ポートとWS中継設定を上書き
$env:UCAR_HTTP_HOST = '127.0.0.1'
$env:UCAR_HTTP_PORT = '8789'   # リレー(WS)と被らないよう受信HTTPは8789に変更
$env:UCAR_WSS        = 'ws://127.0.0.1:8787/alerts'
$env:UCAR_PUSH_TOKEN = '<PUSH_TOKEN>'  # または $env:PUSH_TOKEN
$env:UCAR_CLIENT_ID  = 'minato-pc-01'  # または $env:CLIENT_ID

python .\ucar_rt_listener.py
```

または

```powershell
uvicorn ucar_rt_listener:app --host 127.0.0.1 --port 8787
```

### Windows ファイアウォールについて

ループバック（`127.0.0.1`）のみで待ち受けるため、通常は追加の許可は不要です。警告が表示された場合はローカルネットワークに限定して許可してください。

### 動作テスト（PowerShell）

```powershell
$body = @{
  ts = [double]((Get-Date -UFormat %s) + "." + (Get-Date).Millisecond)
  level = "warn"
  message = "148.250タッチ、高値更新"
  meta = @{ symbol = "USDJPY"; price = 148.250; spread = 0.3 }
}
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8787/alert" -Body ($body | ConvertTo-Json -Depth 5) -ContentType "application/json"
```

### 動作テスト（curl for Windows）

```powershell
curl -X POST "http://127.0.0.1:8787/alert" ^
  -H "Content-Type: application/json" ^
  -d "{""ts"": $(python - <<^PY
import time; print(time.time())
^PY
), ""level"": ""info"", ""message"": ""テスト通知"", ""meta"": {""symbol"": ""USDJPY""}}"
```

### リレー経由のテスト（curl）

```bash
curl -X POST "http://<relay-host>:8787/push" \
  -H "Authorization: Bearer <PUSH_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "target":"minato-pc-01",
    "payload": { "ts": 1723456789.321, "level":"info",
      "message":"【UCAR→直送】CPI: 初動上ヒゲ", "meta":{"symbol":"USDJPY","price":148.19} }
  }'
```

### ログ保存先

`C:\\Users\\<あなたのユーザー名>\\Documents\\UCAR\\RealtimeVoice\\logs\\YYYY\\YYYY-MM\\YYYY-MM-DD_RT-Log.txt`

例（1行）:

```text
[08:45:32.417] WARN 148.250タッチ、高値更新 {"symbol": "USDJPY", "price": 148.25, "spread": 0.3}
```

### 停止方法

起動したターミナルで `Ctrl + C`。

### 補足

- 初回、Windows の通知がオフだとトーストが見えない場合があります。設定 → システム → 通知 で Python（またはターミナル）からの通知を許可してください。
- 本ツールは例外発生時でも HTTP 200 で `{ "ok": true }` を返し、通知失敗時は `toast_error` を含めます。
- タイムスタンプはローカル現在時刻（`datetime.now()`）をミリ秒まで表示します。



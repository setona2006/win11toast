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

### 起動

どちらでもOKです。

```powershell
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



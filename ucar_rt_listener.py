from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Literal

import json
import os
import asyncio
import time
import threading
import traceback

from fastapi import FastAPI
from pydantic import BaseModel, Field
import uvicorn

try:
    # .env 読込（PUSH_TOKEN/ALLOW_CLIENTS ほか）
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

TOAST_BACKEND = "none"
_toast_winotify = None
_toast_win10 = None
_toast_win11 = None

# 優先: winotify → win10toast → win11toast（win11toastはwinsdkビルドが必要なため任意）
try:
    from winotify import Notification, audio  # type: ignore

    def _toast_winotify(title: str, msg: str) -> Optional[str]:
        try:
            n = Notification(app_id="UCAR", title=title, msg=msg, duration="short")
            n.set_audio(audio.Default, loop=False)
            n.show()
            return None
        except Exception:
            return traceback.format_exc()

    TOAST_BACKEND = "winotify"
except Exception:
    pass

if TOAST_BACKEND == "none":
    try:
        from win10toast import ToastNotifier  # type: ignore

        _TOASTER = ToastNotifier()

        def _toast_win10(title: str, msg: str) -> Optional[str]:
            try:
                _TOASTER.show_toast(title, msg, duration=3, threaded=True)
                return None
            except Exception:
                return traceback.format_exc()

        TOAST_BACKEND = "win10toast"
    except Exception:
        pass

if TOAST_BACKEND == "none":
    try:
        from win11toast import toast as _win11_toast  # type: ignore

        def _toast_win11(title: str, msg: str) -> Optional[str]:
            try:
                _win11_toast(title, msg)
                return None
            except Exception:
                return traceback.format_exc()

        TOAST_BACKEND = "win11toast"
    except Exception:
        TOAST_BACKEND = "none"

# トースト無効化（CIやサーバー運用時など）
if os.getenv("UCAR_DISABLE_TOAST", "0") == "1":
    TOAST_BACKEND = "none"

# WS クライアント（オプション）
try:
    import websockets  # type: ignore
except Exception:
    websockets = None


class Alert(BaseModel):
    """アラート受信用モデル。

    - ts: 送信側のエポック秒（受信処理では未使用、受信検証用）
    - level: info | warn | error
    - message: 本文
    - meta: 任意の付加情報オブジェクト
    """

    ts: float = Field(..., description="Epoch seconds (float)")
    level: Literal["info", "warn", "error"] = Field(
        ..., description='One of: "info" | "warn" | "error"'
    )
    message: str
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict)


app = FastAPI(title="UCAR Realtime Alert Listener", version="1.0.0")

# ログベースディレクトリ: ~/Documents/UCAR/RealtimeVoice/logs/YYYY/YYYY-MM/
BASE_DIR = Path.home() / "Documents" / "UCAR" / "RealtimeVoice" / "logs"
BASE_DIR.mkdir(parents=True, exist_ok=True)


def _today_log_path(now: Optional[datetime] = None) -> Path:
    """本日分のログファイルパスを返す。必要に応じてディレクトリも作成。"""
    current = now or datetime.now()
    year_str = f"{current.year:04d}"
    year_month_str = f"{current.year:04d}-{current.month:02d}"
    y_dir = BASE_DIR / year_str / year_month_str
    y_dir.mkdir(parents=True, exist_ok=True)
    return y_dir / f"{current.strftime('%Y-%m-%d')}_RT-Log.txt"


def _format_local_now_ms(now: Optional[datetime] = None) -> str:
    """ローカル現在時刻をミリ秒までの文字列で返す。例: 12:34:56.789"""
    current = now or datetime.now()
    return current.strftime("%H:%M:%S.%f")[:-3]


def _append_log_line(line: str, now: Optional[datetime] = None) -> None:
    log_path = _today_log_path(now)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)


def _show_toast(title: str, msg: str) -> Optional[str]:
    """トースト表示。失敗時は例外文字列を返す（HTTP応答へ含める用）。"""
    if TOAST_BACKEND == "none":
        return "toast backend not available"
    if TOAST_BACKEND == "win11toast" and _toast_win11 is not None:
        return _toast_win11(title, msg)
    if TOAST_BACKEND == "winotify" and _toast_winotify is not None:
        return _toast_winotify(title, msg)
    if TOAST_BACKEND == "win10toast" and _toast_win10 is not None:
        return _toast_win10(title, msg)
    return "toast backend not available"


# --- WebSocket クライアント（クラウドのリレーへ接続） -------------------------
UCAR_WSS = os.getenv("UCAR_WSS", "ws://127.0.0.1:8787/alerts")
# トークン/クライアントIDは UCAR_ プレフィクス付き/無しの両方を許容
ACCESS_TOKEN = os.getenv("UCAR_PUSH_TOKEN") or os.getenv("PUSH_TOKEN", "CHANGE_ME")
CLIENT_ID = os.getenv("UCAR_CLIENT_ID") or os.getenv("CLIENT_ID", "minato-pc-01")


_ws_thread_started = False


def start_ws_in_background() -> None:
    global _ws_thread_started
    if _ws_thread_started:
        return
    if websockets is None:
        print("[WS] disabled: websockets package not installed")
        _ws_thread_started = True  # avoid repeated logs
        return
    if not UCAR_WSS:
        print("[WS] disabled: UCAR_WSS is empty")
        _ws_thread_started = True
        return
    threading.Thread(target=lambda: asyncio.run(_ws_loop()), daemon=True).start()
    _ws_thread_started = True


async def _ws_loop() -> None:
    if not UCAR_WSS or websockets is None:
        return
    import httpx  # type: ignore

    while True:
        try:
            print(f"[WS] connecting -> {UCAR_WSS} as {CLIENT_ID}")
            headers = {
                "Authorization": f"Bearer {ACCESS_TOKEN}",
                "X-Client-ID": CLIENT_ID,
            }
            # websockets のバージョン差異に対応
            try:
                async with websockets.connect(
                    UCAR_WSS,
                    additional_headers=headers,  # websockets >= 11
                    ping_interval=20,
                    ping_timeout=10,
                    max_size=1_000_000,
                ) as ws:
                    print("[WS] connected OK")
                    while True:
                        msg = await ws.recv()
                        try:
                            payload = json.loads(msg)
                            local_host = os.getenv("UCAR_HTTP_HOST", "127.0.0.1")
                            try:
                                local_port = int(os.getenv("UCAR_HTTP_PORT", "8789"))
                            except ValueError:
                                local_port = 8789
                            url = f"http://{local_host}:{local_port}/alert"
                            with httpx.Client(timeout=5.0) as client:
                                r = client.post(url, json=payload)
                                print(f"[WS] forwarded to {url} status={r.status_code}")
                        except Exception as e:
                            print(f"[WS] forward error: {e!r}")
            except TypeError:
                async with websockets.connect(
                    UCAR_WSS,
                    extra_headers=headers,  # websockets <= 10
                    ping_interval=20,
                    ping_timeout=10,
                    max_size=1_000_000,
                ) as ws:
                    print("[WS] connected OK")
                    while True:
                        msg = await ws.recv()
                        try:
                            payload = json.loads(msg)
                            local_host = os.getenv("UCAR_HTTP_HOST", "127.0.0.1")
                            try:
                                local_port = int(os.getenv("UCAR_HTTP_PORT", "8789"))
                            except ValueError:
                                local_port = 8789
                            url = f"http://{local_host}:{local_port}/alert"
                            with httpx.Client(timeout=5.0) as client:
                                r = client.post(url, json=payload)
                                print(f"[WS] forwarded to {url} status={r.status_code}")
                        except Exception as e:
                            # 受信エラーは握りつぶして継続
                            print(f"[WS] forward error: {e!r}")
        except Exception as e:
            print(f"[WS] disconnected - retry in 3s ({e!r})")
            time.sleep(3)


@app.on_event("startup")
async def _on_startup_ws() -> None:
    # Uvicorn経由起動（`uvicorn ucar_rt_listener:app`）でもWSを開始する
    try:
        start_ws_in_background()
    except Exception:
        pass


@app.post("/alert")
def receive_alert(a: Alert) -> Dict[str, Any]:
    """UCARクラウドからのアラートを受信し、ログ追記とトースト通知を行う。"""
    now = datetime.now()
    ts_local = _format_local_now_ms(now)

    # ログ行: [HH:MM:SS.mmm] LEVEL MESSAGE {meta-json}
    meta_json = json.dumps(a.meta or {}, ensure_ascii=False)
    line = f"[{ts_local}] {a.level.upper()} {a.message} {meta_json}\n"

    # 1) ログ追記（失敗しても落とさない）
    try:
        _append_log_line(line, now)
    except Exception:
        # ログ失敗しても処理継続（応答は常に200）
        pass

    # 2) トースト通知（失敗しても落とさない）
    toast_err = _show_toast("UCAR Alert", f"{a.message}  ({ts_local})")

    # 失敗してもHTTP 200で返す。toast_errorは必要時のみ含める。
    response: Dict[str, Any] = {"ok": True}
    if toast_err:
        response["toast_error"] = toast_err
    return response


if __name__ == "__main__":
    # リレーが設定されていればバックグラウンドでWS接続
    try:
        start_ws_in_background()
    except Exception:
        pass
    # ローカル限定で待ち受け（環境変数で上書き可能）
    host = os.getenv("UCAR_HTTP_HOST", "127.0.0.1")
    try:
        # 受信HTTPはデフォルト8789（8787はWSリレー用）
        port = int(os.getenv("UCAR_HTTP_PORT", "8789"))
    except ValueError:
        port = 8789
    uvicorn.run(app, host=host, port=port, log_level="info")

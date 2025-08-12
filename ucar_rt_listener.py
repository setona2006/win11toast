from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Literal

import json
import traceback

from fastapi import FastAPI
from pydantic import BaseModel, Field
import uvicorn

try:
    from win10toast import ToastNotifier

    TOASTER = ToastNotifier()
except Exception:
    TOASTER = None  # 通知不可でもログは動かす


class Alert(BaseModel):
    """アラート受信用モデル。

    - ts: 送信側のエポック秒（受信処理では未使用、受信検証用）
    - level: info | warn | error
    - message: 本文
    - meta: 任意の付加情報オブジェクト
    """

    ts: float = Field(..., description="エポック秒（float）")
    level: Literal["info", "warn", "error"] = Field(
        ..., description='次のいずれか: "info" | "warn" | "error"'
    )
    message: str
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict)


app = FastAPI(title="UCAR リアルタイムアラートリスナー", version="1.0.0")

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
    if TOASTER is None:
        return "win10toast を使用できません（インポート失敗）"
    try:
        # 非ブロッキングで3秒表示
        TOASTER.show_toast(title, msg, duration=3, threaded=True)
        return None
    except Exception:
        return traceback.format_exc()


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
    # ローカル限定で待ち受け
    uvicorn.run(app, host="127.0.0.1", port=8787, log_level="info")

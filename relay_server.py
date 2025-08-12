"""UCAR WebSocket Relay (Python版)

最小のWSリレー: `/alerts` にクライアント（ローカル端末）が接続、`/push` でクラウド側から送信。

起動例:
  pip install -r requirements.txt
  uvicorn relay_server:app --host 0.0.0.0 --port 8787
"""

from __future__ import annotations

import json
import os
from typing import Dict

from fastapi import FastAPI, Request, HTTPException
from starlette.websockets import WebSocket, WebSocketDisconnect

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # .env 無しでも動かす
    pass

PUSH_TOKEN = os.getenv("PUSH_TOKEN", "CHANGE_ME_PUSH_TOKEN")
ALLOW_CLIENTS = set(os.getenv("ALLOW_CLIENTS", "minato-pc-01").split(","))

app = FastAPI(title="UCAR WS Relay")

# 接続中クライアント: clientId -> WebSocket
clients: Dict[str, WebSocket] = {}


@app.websocket("/alerts")
async def alerts(ws: WebSocket):
    # WebSocketはHeader依存性注入が効かない環境があるため、直接参照
    authorization = ws.headers.get("authorization", "")
    x_client_id = ws.headers.get("x-client-id")
    # 簡易認証（必要に応じて強化）
    if not authorization.startswith("Bearer ") or not x_client_id:
        await ws.close(code=4001)
        return
    token = authorization[7:]
    if token != PUSH_TOKEN or x_client_id not in ALLOW_CLIENTS:
        await ws.close(code=4003)
        return

    await ws.accept()
    clients[x_client_id] = ws
    try:
        while True:
            # クライアントから送るものは特にない想定。受信は捨てる/生存確認用。
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if clients.get(x_client_id) is ws:
            del clients[x_client_id]


@app.post("/push")
async def push(req: Request):
    auth = req.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != PUSH_TOKEN:
        raise HTTPException(401, "unauthorized")

    body = await req.json()
    target = body.get("target")
    payload = body.get("payload")
    if not target or not payload:
        raise HTTPException(400, "bad_request")

    ws = clients.get(target)
    if not ws:
        raise HTTPException(404, "client_not_connected")

    await ws.send_text(json.dumps(payload, ensure_ascii=False))
    return {"ok": True}


@app.get("/health")
def health():
    return {"ok": True, "clients": list(clients.keys())}

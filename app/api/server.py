"""FastAPI app: REST snapshot + WebSocket stream + static dashboard."""
from __future__ import annotations
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uuid

from app.core.engine import Engine
from app.config import settings

log = logging.getLogger("api")

clients: set[WebSocket] = set()
engine: Engine | None = None
# Simple in-memory token store (private app). Tokens live until server restarts.
valid_tokens: set[str] = set()


class LoginRequest(BaseModel):
    code: str


async def broadcast(snapshot: dict) -> None:
    if not clients:
        return
    payload = json.dumps(snapshot, default=str)
    dead = []
    for ws in clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    engine = Engine(broadcaster=broadcast)
    await engine.start()
    log.info("Engine started")
    try:
        yield
    finally:
        await engine.stop()
        log.info("Engine stopped")


app = FastAPI(title="MT5 Execution Intelligence", lifespan=lifespan)

static_dir = os.path.join(os.path.dirname(__file__), "..", "web", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.post('/api/login')
async def login(req: LoginRequest):
    # simple shared-code authentication
    if not settings.access_code:
        raise HTTPException(status_code=500, detail='Access code not configured on server')
    if req.code == settings.access_code:
        token = str(uuid.uuid4())
        valid_tokens.add(token)
        return JSONResponse({"token": token})
    raise HTTPException(status_code=401, detail='Invalid code')


def _validate_token(token: str | None) -> bool:
    return bool(token and token in valid_tokens)


@app.get("/api/snapshot")
async def snapshot(request: Request) -> JSONResponse:
    # Accept token via header (Authorization: Bearer <token>) or query param or cookie
    token = None
    auth = request.headers.get('authorization')
    if auth and auth.lower().startswith('bearer '):
        token = auth.split(' ', 1)[1].strip()
    if not token:
        token = request.query_params.get('token') or request.cookies.get('access_token')
    if not _validate_token(token):
        raise HTTPException(status_code=401, detail='Unauthorized')
    data = engine.latest if engine else {}
    return JSONResponse(json.loads(json.dumps(data, default=str)))


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "connected": engine.client.connected if engine else False}


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    # Require token in query params: /ws?token=...
    token = websocket.query_params.get('token')
    if not _validate_token(token):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    clients.add(websocket)
    try:
        if engine and engine.latest:
            await websocket.send_text(json.dumps(engine.latest, default=str))
        while True:
            await websocket.receive_text()  # keep-alive
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(websocket)

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
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

from app.core.engine import Engine
from app.config import settings
from app.core.sync_service import SyncServiceManager
from app.api import sync_routes

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
    
    # Initialize MT5 real-time sync if enabled
    if os.getenv('MOCK_MODE', '1') == '0':
        log.info("🔄 Initializing real-time MT5 sync service...")
        try:
            mt5_login = os.getenv('MT5_LOGIN')
            mt5_password = os.getenv('MT5_PASSWORD')
            mt5_server = os.getenv('MT5_SERVER')
            mt5_path = os.getenv('MT5_PATH')
            poll_interval = int(os.getenv('POLL_INTERVAL_SECONDS', '5'))
            
            if mt5_login and mt5_password and mt5_server:
                sync_service = SyncServiceManager.initialize(
                    mt5_login=int(mt5_login),
                    mt5_password=mt5_password,
                    mt5_server=mt5_server,
                    mt5_path=mt5_path,
                    poll_interval=poll_interval,
                )
                
                # Connect and start syncing
                if sync_service.connect():
                    sync_service.start()
                    log.info("✅ Real-time sync service started successfully")
                else:
                    log.warning("⚠️ Failed to connect to MT5 - running in cached mode")
            else:
                log.warning("⚠️ MT5 credentials not configured")
        except Exception as e:
            log.error(f"Error initializing sync service: {e}")
    else:
        log.info("📋 Running in MOCK_MODE - real-time sync disabled")
    
    engine = Engine(broadcaster=broadcast)
    await engine.start()
    log.info("Engine started")
    try:
        yield
    finally:
        await engine.stop()
        # Stop sync service on shutdown
        SyncServiceManager.stop()
        log.info("Engine stopped")


app = FastAPI(title="MT5 Execution Intelligence", lifespan=lifespan)

# Add CORS middleware to allow requests from Netlify frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins; can restrict to specific URLs like "https://turbo-executions.netlify.app"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    from app.core.sync_service import SyncServiceManager
    sync_service = SyncServiceManager.get_instance()
    sync_status = sync_service.get_status() if sync_service else {}
    
    return {
        "ok": True,
        "connected": engine.client.connected if engine else False,
        "sync_service": {
            "running": sync_status.get('running', False),
            "connected": sync_status.get('connected', False),
            "last_sync": sync_status.get('last_sync'),
        }
    }


# Include real-time sync routes
app.include_router(sync_routes.router)


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

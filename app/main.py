from __future__ import annotations

import asyncio
import json
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.ai import list_engines, pikafish, shutdown
from app.ai.zzh import save_uploaded_pt
from app.catalog import DEVELOPER, PROJECT_NAME, PROJECT_TITLE, clamp_level, public_meta
from app.config import PORT, TUNNEL, WEB_DIR
from app.rooms import Client, clean_name, manager
from app.tunnel import Tunnel, lan_urls

PUBLIC_URLS: dict[str, list[str]] = {"local": [], "public": []}
_tunnel: Tunnel | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _tunnel
    port = int(os.environ.get("XIANGQI_PORT", PORT))
    local = lan_urls(port)
    public = None
    if TUNNEL not in ("off", "0", "false"):
        _tunnel = Tunnel(port)
        public = await asyncio.get_running_loop().run_in_executor(None, _tunnel.start)
    bind_public_urls(local, public)
    print("访问链接:", flush=True)
    for u in local:
        print(f"  {u}", flush=True)
    if public:
        print(f"  公网分享: {public}", flush=True)
    else:
        print("  未获得公网隧道，可用局域网地址分享给同网段对手", flush=True)
    await asyncio.get_running_loop().run_in_executor(
        None, lambda: pikafish().available() and pikafish()._engine()
    )
    yield
    shutdown()
    if _tunnel:
        _tunnel.stop()


app = FastAPI(title=PROJECT_NAME, version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


@app.get("/")
async def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/health")
async def health():
    engines = list_engines()
    meta = public_meta()
    return {
        "ok": True,
        "version": __version__,
        "name": PROJECT_NAME,
        "title": PROJECT_TITLE,
        "developer": DEVELOPER,
        "engines": engines,
        "urls": PUBLIC_URLS,
        "rooms": len(manager.rooms),
        "default_mode": meta["default_mode"],
        "github": meta["github"],
    }


@app.get("/api/info")
async def info():
    meta = public_meta()
    return JSONResponse({
        "version": __version__,
        "engines": list_engines(),
        "urls": PUBLIC_URLS,
        **meta,
    })


@app.get("/api/modes")
async def api_modes():
    return JSONResponse(public_meta())


@app.get("/api/ais")
async def api_ais(mode: str = "jieqi"):
    return JSONResponse({"mode": mode, "engines": list_engines(mode)})


@app.post("/api/local-ai")
async def api_local_ai(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 120 * 1024 * 1024:
        return JSONResponse({"ok": False, "message": "文件过大（上限 120MB）"}, status_code=400)
    try:
        dest = save_uploaded_pt(file.filename or "upload.pt", data)
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "id": f"pt:local/{dest.name}", "name": f"本地 {dest.stem}", "path": dest.name})


@app.websocket("/ws")
async def websocket_game(ws: WebSocket):
    await ws.accept()
    client = Client(ws=ws, client_id=secrets.token_hex(8), name="棋友")
    room_id: str | None = None
    try:
        await ws.send_json({"type": "hello", "client_id": client.client_id, "info": {
            "engines": list_engines(),
            "urls": PUBLIC_URLS,
            "version": __version__,
            **public_meta(),
        }})
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "消息不是合法 JSON"})
                continue
            mtype = msg.get("type")
            try:
                if mtype == "create":
                    if room_id:
                        await manager.drop_client(room_id, client.client_id)
                    client.name = clean_name(msg.get("name"))
                    room = await manager.create(
                        mode=msg.get("mode") or "jieqi",
                        color=msg.get("color") or "w",
                        vs=msg.get("vs") or "ai",
                        level=int(msg.get("level") or 5),
                        engine_id=msg.get("engine") or "auto",
                        client=client,
                        w_engine=msg.get("w_engine"),
                        b_engine=msg.get("b_engine"),
                        w_level=msg.get("w_level"),
                        b_level=msg.get("b_level"),
                    )
                    room_id = room.id
                    await ws.send_json({
                        "type": "joined",
                        "room": room.id,
                        "role": client.role,
                        "share_url": manager.share_url(room.id),
                    })
                    await manager.broadcast(room, {"type": "state", **manager.snapshot(room)})
                    await manager.maybe_ai(room)
                elif mtype == "join":
                    if room_id:
                        await manager.drop_client(room_id, client.client_id)
                    client.name = clean_name(msg.get("name"))
                    room = await manager.join(msg.get("room") or "", client, prefer=msg.get("color"))
                    room_id = room.id
                    await ws.send_json({
                        "type": "joined",
                        "room": room.id,
                        "role": client.role,
                        "share_url": manager.share_url(room.id),
                    })
                    await manager.broadcast(room, {"type": "state", **manager.snapshot(room)})
                elif mtype == "move":
                    if not room_id:
                        raise ValueError("尚未进入房间")
                    room = manager.get(room_id)
                    if not room:
                        raise ValueError("房间已关闭")
                    iccs = (msg.get("iccs") or "").strip().lower()
                    extra = {k: msg[k] for k in ("as_type", "guess") if msg.get(k)}
                    await manager.apply_move(room, iccs, by=client, extra=extra)
                    await manager.maybe_ai(room)
                elif mtype == "seat":
                    if not room_id:
                        raise ValueError("尚未进入房间")
                    room = manager.get(room_id)
                    await manager.set_seat(
                        room,
                        msg.get("color"),
                        msg.get("kind"),
                        client,
                        engine_id=msg.get("engine"),
                        level=msg.get("level"),
                    )
                elif mtype == "new_game":
                    if not room_id:
                        raise ValueError("尚未进入房间")
                    room = manager.get(room_id)
                    await manager.new_game(room, msg.get("mode"))
                elif mtype == "resign":
                    if not room_id:
                        raise ValueError("尚未进入房间")
                    await manager.resign(manager.get(room_id), client)
                elif mtype == "level":
                    if not room_id:
                        raise ValueError("尚未进入房间")
                    room = manager.get(room_id)
                    async with room.lock:
                        room.level = clamp_level(msg.get("level") or 5)
                    await manager.broadcast(room, {"type": "state", **manager.snapshot(room)})
                elif mtype == "ping":
                    await ws.send_json({"type": "pong"})
                else:
                    await ws.send_json({"type": "error", "message": f"未知消息: {mtype}"})
            except Exception as exc:
                try:
                    await ws.send_json({"type": "error", "message": str(exc)})
                except Exception:
                    break
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        if room_id:
            await manager.drop_client(room_id, client.client_id)


def bind_public_urls(local: list[str], public: str | None) -> None:
    PUBLIC_URLS["local"] = local
    PUBLIC_URLS["public"] = [public] if public else []
    if public:
        manager.set_public_base(public)
    elif local:
        # 优先局域网地址便于分享
        lan = next((u for u in local if "127.0.0.1" not in u), local[0])
        manager.set_public_base(lan)

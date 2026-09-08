from __future__ import annotations

import asyncio
import json
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from app.ai import choose_move, list_engines, narrator
from app.ai.base import MoveRequest
from app.catalog import ai_profile, clamp_level, mode_info
from app.game import create_game

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_room_id() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def _engine_label(engine_id: str, mode: str) -> str:
    eid = (engine_id or "auto").lower()
    for e in list_engines(mode):
        if e["id"] == eid:
            return e["name"]
    if eid in ("auto", ""):
        return "自动"
    if eid.startswith("pt:"):
        return eid.split("/")[-1]
    return eid


@dataclass
class Seat:
    kind: str = "human"  # human | ai
    client_id: str | None = None
    name: str = ""
    engine_id: str = "auto"
    level: int | None = None
    checkpoint: str | None = None


@dataclass
class Client:
    ws: WebSocket
    client_id: str
    name: str
    role: str = "spectator"  # w / b / spectator


@dataclass
class Room:
    id: str
    mode: str
    game: Any
    level: int = 5
    engine_id: str = "auto"
    seats: dict[str, Seat] = field(default_factory=lambda: {"w": Seat(), "b": Seat(kind="ai")})
    clients: dict[str, Client] = field(default_factory=dict)
    created: float = field(default_factory=time.time)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    ai_busy: bool = False

    def occupant(self, color: str) -> Client | None:
        seat = self.seats[color]
        if seat.client_id and seat.client_id in self.clients:
            return self.clients[seat.client_id]
        return None


class RoomManager:
    def __init__(self):
        self.rooms: dict[str, Room] = {}
        self.lock = asyncio.Lock()
        self.public_base: str = ""

    def set_public_base(self, url: str) -> None:
        self.public_base = url.rstrip("/")

    def share_url(self, room_id: str) -> str:
        base = self.public_base or ""
        if not base:
            return f"/?room={room_id}"
        return f"{base}/?room={room_id}"

    async def create(
        self,
        mode: str,
        color: str,
        vs: str,
        level: int,
        engine_id: str,
        client: Client,
        seed: int | None = None,
        w_engine: str | None = None,
        b_engine: str | None = None,
        w_level: int | None = None,
        b_level: int | None = None,
    ) -> Room:
        async with self.lock:
            rid = new_room_id()
            while rid in self.rooms:
                rid = new_room_id()
            game = create_game(mode, seed=seed)
            color = "w" if color in ("w", "red", "红") else "b"
            vs = vs if vs in ("ai", "human", "aivsai") else "ai"
            default_engine = engine_id or "auto"
            default_level = clamp_level(level)
            if vs == "aivsai":
                we = (w_engine or default_engine or "auto")
                be = (b_engine or default_engine or "auto")
                wl = clamp_level(w_level if w_level is not None else default_level)
                bl = clamp_level(b_level if b_level is not None else default_level)
                seats = {
                    "w": Seat(kind="ai", engine_id=we, level=wl, name=_engine_label(we, game.mode)),
                    "b": Seat(kind="ai", engine_id=be, level=bl, name=_engine_label(be, game.mode)),
                }
                client.role = "spectator"
                if getattr(game, "mode", "") == "zhencha" and hasattr(game, "auto_ready_ai"):
                    game.auto_ready_ai("w")
                    game.auto_ready_ai("b")
            else:
                other = "b" if color == "w" else "w"
                seats = {
                    color: Seat(kind="human", client_id=client.client_id, name=client.name),
                    other: Seat(
                        kind="ai" if vs == "ai" else "human",
                        engine_id=default_engine,
                        level=default_level,
                        name=_engine_label(default_engine, game.mode) if vs == "ai" else "",
                    ),
                }
                client.role = color
                if getattr(game, "mode", "") == "zhencha" and vs == "ai" and hasattr(game, "auto_ready_ai"):
                    game.auto_ready_ai(other)
            room = Room(
                id=rid,
                mode=game.mode,
                game=game,
                level=default_level,
                engine_id=default_engine,
                seats=seats,
            )
            room.clients[client.client_id] = client
            self.rooms[rid] = room
            return room

    async def join(self, room_id: str, client: Client, prefer: str | None = None) -> Room:
        room = self.rooms.get((room_id or "").upper())
        if not room:
            raise ValueError("房间不存在")
        async with room.lock:
            room.clients[client.client_id] = client
            free = [c for c, s in room.seats.items() if s.kind == "human" and not s.client_id]
            if prefer in ("w", "b") and prefer in free:
                chosen = prefer
            elif free:
                chosen = free[0]
            else:
                client.role = "spectator"
                return room
            seat = room.seats[chosen]
            seat.client_id = client.client_id
            seat.name = client.name
            client.role = chosen
            return room

    def get(self, room_id: str) -> Room | None:
        return self.rooms.get((room_id or "").upper())

    async def drop_client(self, room_id: str, client_id: str) -> None:
        room = self.get(room_id)
        if not room:
            return
        async with room.lock:
            room.clients.pop(client_id, None)
            for seat in room.seats.values():
                if seat.client_id == client_id:
                    seat.client_id = None
                    if seat.kind == "human":
                        seat.name = ""

    def snapshot(self, room: Room) -> dict[str, Any]:
        state = room.game.observer_state()
        info = mode_info(room.mode)
        prof = ai_profile(room.mode, room.level)
        state.update({
            "room": room.id,
            "share_url": self.share_url(room.id),
            "level": room.level,
            "engine_id": room.engine_id,
            "mode_name": info["name"],
            "ai_profile": prof,
            "engines": list_engines(room.mode),
            "seats": {
                color: {
                    "kind": seat.kind,
                    "occupied": bool(seat.client_id),
                    "name": seat.name or ("AI" if seat.kind == "ai" else "空位"),
                    "engine_id": seat.engine_id,
                    "level": seat.level if seat.level is not None else room.level,
                }
                for color, seat in room.seats.items()
            },
            "viewers": len(room.clients),
        })
        return state

    async def broadcast(self, room: Room, payload: dict) -> None:
        dead = []
        data = json.dumps(payload, ensure_ascii=False)
        for cid, client in list(room.clients.items()):
            try:
                await client.ws.send_text(data)
            except Exception:
                dead.append(cid)
        for cid in dead:
            room.clients.pop(cid, None)

    async def apply_move(self, room: Room, iccs: str, by: Client | None, as_ai: bool = False, extra: dict | None = None) -> dict:
        extra = extra or {}
        async with room.lock:
            if room.game.over:
                raise ValueError("对局已结束")
            side = room.game.side
            seat = room.seats[side]
            if not as_ai:
                if seat.kind == "ai":
                    raise ValueError("当前轮到 AI 行棋")
                if seat.client_id and by and seat.client_id != by.client_id:
                    raise ValueError("还没轮到你")
            kwargs = {k: extra[k] for k in ("as_type", "guess", "validate") if k in extra}
            event = room.game.apply(iccs, **kwargs)
        state = self.snapshot(room)
        state["event"] = event
        note = ""
        if event.get("flip"):
            names = state.get("names") or {}
            note = f"翻开 {names.get(event['flip'], event['flip'])}"
        if event.get("captured_name"):
            note = (note + "，" if note else "") + f"吃 {event['captured_name']}"
        elif event.get("captured"):
            names = state.get("names") or {}
            note = (note + "，" if note else "") + f"吃 {names.get(event['captured'], event['captured'])}"
        if event.get("suicide"):
            note = (note + "，" if note else "") + "猜错自损"
        if event.get("check"):
            note = (note + "，" if note else "") + "将军"
        if room.game.over:
            if room.game.winner == "draw":
                note = "和棋"
            elif room.game.winner == "w":
                note = "红胜"
            else:
                note = "黑胜"
        state["banner"] = note
        await self.broadcast(room, {"type": "state", **state})
        return state

    async def maybe_ai(self, room: Room) -> None:
        async with room.lock:
            if room.game.over:
                return
            side = room.game.side
            seat = room.seats[side]
            if seat.kind != "ai" or room.ai_busy:
                return
            room.ai_busy = True
            game = room.game
            level = seat.level if seat.level is not None else room.level
            engine_id = seat.engine_id or room.engine_id
            checkpoint = seat.checkpoint
            legal = game.legal_moves()
            fen = game.fen()
            behavior = getattr(game, "behavior_fen", lambda: "")()
            mode = game.mode
        both_ai = room.seats["w"].kind == "ai" and room.seats["b"].kind == "ai"
        if both_ai:
            await asyncio.sleep(0.35)
        moved = False
        try:
            extra: dict[str, Any] = {"game": game, "behavior_fen": behavior}
            if checkpoint:
                extra["checkpoint"] = checkpoint
            req = MoveRequest(
                mode=mode,
                fen=fen,
                legal_moves=legal,
                side=side,
                level=level,
                extra=extra,
            )
            resp = await asyncio.get_running_loop().run_in_executor(
                None, lambda: choose_move(req, engine_id)
            )
            if not resp.move:
                return
            await self.apply_move(room, resp.move, by=None, as_ai=True)
            moved = True
            comment = resp.comment
            n = narrator()
            if n.available():
                try:
                    extra_c = await asyncio.get_running_loop().run_in_executor(
                        None,
                        lambda: n.comment(room.game.mode, resp.move, room.game.fen(), room.game.last_event),
                    )
                    if extra_c:
                        comment = extra_c
                except Exception:
                    pass
            label = _engine_label(engine_id, mode)
            await self.broadcast(room, {
                "type": "ai_comment",
                "engine": resp.engine,
                "engine_name": label,
                "side": side,
                "fallback": resp.fallback,
                "comment": comment,
                "move": resp.move,
            })
        finally:
            room.ai_busy = False
            if moved and not room.game.over and room.seats[room.game.side].kind == "ai":
                asyncio.create_task(self.maybe_ai(room))

    async def set_seat(self, room: Room, color: str, kind: str, client: Client | None, engine_id: str | None = None, level: int | None = None) -> None:
        if color not in ("w", "b"):
            raise ValueError("颜色无效")
        if kind not in ("human", "ai"):
            raise ValueError("席位类型无效")
        async with room.lock:
            seat = room.seats[color]
            seat.kind = kind
            if engine_id:
                seat.engine_id = engine_id
            if level is not None:
                seat.level = clamp_level(level)
            if kind == "ai":
                seat.client_id = None
                seat.name = _engine_label(seat.engine_id, room.mode)
            elif client and not seat.client_id:
                seat.client_id = client.client_id
                seat.name = client.name
                client.role = color
        await self.broadcast(room, {"type": "state", **self.snapshot(room)})
        await self.maybe_ai(room)

    async def new_game(self, room: Room, mode: str | None = None) -> None:
        async with room.lock:
            room.mode = mode or room.mode
            room.game = create_game(room.mode)
            room.ai_busy = False
            if room.seats["w"].kind == "ai" and room.seats["b"].kind == "ai":
                if getattr(room.game, "mode", "") == "zhencha" and hasattr(room.game, "auto_ready_ai"):
                    room.game.auto_ready_ai("w")
                    room.game.auto_ready_ai("b")
        await self.broadcast(room, {"type": "state", **self.snapshot(room)})
        await self.maybe_ai(room)

    async def resign(self, room: Room, client: Client) -> None:
        color = client.role
        if color not in ("w", "b"):
            raise ValueError("观战者不能认输")
        async with room.lock:
            if room.game.over:
                return
            room.game.over = True
            room.game.winner = "b" if color == "w" else "w"
        await self.broadcast(room, {"type": "state", **self.snapshot(room), "banner": "认输"})


manager = RoomManager()


SAFE_NAME = re.compile(r"^[\w\u4e00-\u9fff\- ]{1,16}$")


def clean_name(name: str | None) -> str:
    name = (name or "").strip()[:16]
    if name and SAFE_NAME.match(name):
        return name
    return "棋友"

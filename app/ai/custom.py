from __future__ import annotations

import json
from urllib import request

from app.config import CUSTOM_AI_KEY, CUSTOM_AI_URL

from .base import MoveRequest, MoveResponse


class HttpModelEngine:
    """自定义模型接入：向用户服务 POST JSON，约定返回 {"move": "h2e2", "comment": "..."}。"""

    id = "custom-http"
    name = "自定义模型 (HTTP)"
    modes = {"xiangqi", "jieqi"}

    def __init__(self, url: str | None = None, timeout: float = 8.0):
        self.url = (url or CUSTOM_AI_URL).rstrip("/")
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.url)

    def close(self) -> None:
        return None

    def choose_move(self, req: MoveRequest) -> MoveResponse:
        if not self.url:
            return MoveResponse(move="", engine=self.id, comment="未配置 XIANGQI_CUSTOM_AI_URL")
        payload = {
            "mode": req.mode,
            "fen": req.fen,
            "legal_moves": req.legal_moves,
            "side": req.side,
            "level": req.level,
            "extra": {k: v for k, v in (req.extra or {}).items() if k != "game"},
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if CUSTOM_AI_KEY:
            headers["Authorization"] = f"Bearer {CUSTOM_AI_KEY}"
        req_http = request.Request(self.url, data=data, headers=headers, method="POST")
        with request.urlopen(req_http, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        mv = str(body.get("move") or body.get("iccs") or "").strip().lower()
        comment = str(body.get("comment") or "自定义模型")
        return MoveResponse(move=mv, engine=self.id, comment=comment, raw=json.dumps(body, ensure_ascii=False))

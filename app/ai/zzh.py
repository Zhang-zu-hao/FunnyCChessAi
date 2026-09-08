from __future__ import annotations

import os
from pathlib import Path

from app.config import CUSTOM_AI_URL, ROOT

from .base import MoveRequest, MoveResponse
from .custom import HttpModelEngine

ZZH_URL = os.environ.get("XIANGQI_ZZH_URL", "").strip() or CUSTOM_AI_URL
ZZH_DIR = Path(os.environ.get("XIANGQI_ZZH_DIR", ROOT / "engines" / "zzh"))


class ZzhEngine:
    """ZZH 级：自研权重 / HTTP 模型。未接入时回退该玩法最强内置搜索。"""

    id = "zzh"
    name = "ZZH 引擎"
    modes = {"xiangqi", "jieqi", "anqi", "zhencha", "manchu", "bawang", "wuhu"}

    def __init__(self):
        self._http = HttpModelEngine(url=ZZH_URL or None, timeout=12.0) if ZZH_URL else None

    def available(self) -> bool:
        if self._http and self._http.available():
            return True
        return any(ZZH_DIR.glob("*.pt")) or any(ZZH_DIR.glob("*.pth"))

    def close(self) -> None:
        return None

    def choose_move(self, req: MoveRequest) -> MoveResponse:
        if self._http and self._http.available():
            resp = self._http.choose_move(req)
            resp.engine = self.id
            resp.comment = "ZZH · " + (resp.comment or "自定义模型")
            return resp
        ckpt = ZZH_DIR / f"{req.mode}.pt"
        if not ckpt.is_file():
            ckpt = ZZH_DIR / "policy.pt"
        if ckpt.is_file():
            try:
                mv = self._infer_torch(ckpt, req)
                if mv in req.legal_moves:
                    return MoveResponse(move=mv, engine=self.id, comment=f"ZZH 权重 {ckpt.name}")
            except Exception as exc:
                return MoveResponse(move="", engine=self.id, comment=f"ZZH 推理失败 {exc}")
        return MoveResponse(move="", engine=self.id, comment="ZZH 权重未接入")

    def _infer_torch(self, ckpt: Path, req: MoveRequest) -> str:
        import torch
        from train.infer import policy_move
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return policy_move(ckpt, req, device)

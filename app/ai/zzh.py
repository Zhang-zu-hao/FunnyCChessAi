from __future__ import annotations

import os
import re
from pathlib import Path

from app.config import CUSTOM_AI_URL, ROOT

from .base import MoveRequest, MoveResponse
from .custom import HttpModelEngine

SELFTRAIN_URL = os.environ.get("XIANGQI_ZZH_URL", "").strip() or CUSTOM_AI_URL
SELFTRAIN_DIR = Path(os.environ.get("XIANGQI_ZZH_DIR", ROOT / "engines" / "zzh"))
LOCAL_DIR = Path(os.environ.get("XIANGQI_LOCAL_AI_DIR", ROOT / "engines" / "local"))
SAFE_PT = re.compile(r"^[\w.\-]{1,80}\.(pt|pth)$", re.I)


class ZzhEngine:
    """自训练策略网络 / HTTP 模型。未接入时由上层回退内置搜索。"""

    id = "selftrain"
    name = "自训练模型"
    modes = {"xiangqi", "jieqi", "anqi", "zhencha", "manchu", "bawang", "wuhu"}

    def __init__(self):
        self._http = HttpModelEngine(url=SELFTRAIN_URL or None, timeout=12.0) if SELFTRAIN_URL else None

    def available(self) -> bool:
        if self._http and self._http.available():
            return True
        return any(SELFTRAIN_DIR.glob("*.pt")) or any(SELFTRAIN_DIR.glob("*.pth")) or any(LOCAL_DIR.glob("*.pt"))

    def close(self) -> None:
        return None

    def choose_move(self, req: MoveRequest) -> MoveResponse:
        extra = req.extra or {}
        ckpt = extra.get("checkpoint")
        if ckpt:
            path = Path(str(ckpt))
            if path.is_file():
                return self._from_file(path, req)
        if self._http and self._http.available():
            resp = self._http.choose_move(req)
            resp.engine = self.id
            resp.comment = "自训练 HTTP · " + (resp.comment or "自定义模型")
            return resp
        path = SELFTRAIN_DIR / f"{req.mode}.pt"
        if not path.is_file():
            path = SELFTRAIN_DIR / "policy.pt"
        if path.is_file():
            return self._from_file(path, req)
        return MoveResponse(move="", engine=self.id, comment="自训练权重未接入")

    def _from_file(self, ckpt: Path, req: MoveRequest) -> MoveResponse:
        try:
            mv = self._infer_torch(ckpt, req)
            if mv in req.legal_moves:
                return MoveResponse(move=mv, engine=self.id, comment=f"自训练权重 {ckpt.name}")
            return MoveResponse(move="", engine=self.id, comment=f"自训练着法不合法 {ckpt.name}")
        except Exception as exc:
            return MoveResponse(move="", engine=self.id, comment=f"自训练推理失败 {exc}")

    def _infer_torch(self, ckpt: Path, req: MoveRequest) -> str:
        import torch
        from train.infer import policy_move
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return policy_move(ckpt, req, device)


def list_local_checkpoints() -> list[dict]:
    items = []
    for folder, kind in ((SELFTRAIN_DIR, "selftrain"), (LOCAL_DIR, "local")):
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.pt")) + sorted(folder.glob("*.pth")):
            rel = f"{folder.name}/{p.name}"
            stem = p.stem.lower()
            modes = [stem] if stem in ZzhEngine.modes else sorted(ZzhEngine.modes)
            items.append({
                "id": f"pt:{rel}",
                "name": f"{'自训练' if kind == 'selftrain' else '本地'} {p.stem}",
                "path": str(p),
                "kind": kind,
                "available": True,
                "modes": modes,
            })
    return items


def resolve_pt(engine_id: str) -> Path | None:
    eid = (engine_id or "").strip()
    if not eid.startswith("pt:"):
        return None
    rel = eid[3:].replace("\\", "/").lstrip("/")
    parts = Path(rel)
    if parts.name != rel.split("/")[-1] or not SAFE_PT.match(parts.name):
        return None
    if parts.parts[0] not in ("zzh", "local") or len(parts.parts) != 2:
        return None
    path = (ROOT / "engines" / parts).resolve()
    root = (ROOT / "engines").resolve()
    if root not in path.parents:
        return None
    return path if path.is_file() else None


def save_uploaded_pt(filename: str, data: bytes) -> Path:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    name = Path(filename or "upload.pt").name
    if not SAFE_PT.match(name):
        raise ValueError("仅支持字母数字命名的 .pt / .pth 文件")
    dest = LOCAL_DIR / name
    dest.write_bytes(data)
    return dest

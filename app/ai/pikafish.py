from __future__ import annotations

from pathlib import Path

from app.catalog import XIANGQI_DEPTH, XIANGQI_MOVETIME_MS, clamp_level
from app.config import ENGINE_HASH_MB, ENGINE_THREADS, PIKAFISH_BIN, PIKAFISH_NNUE

from .base import MoveRequest, MoveResponse
from .heuristic import HeuristicEngine
from .jieqi_search import JieqiSearchEngine
from .uci import UCIEngine


class PikafishEngine:
    """标准中国象棋：皮卡鱼 UCI。揭棋：规则树搜索（不对局透视暗子真身），开局可向皮卡鱼要提示着。"""

    id = "pikafish"
    name = "皮卡鱼"
    modes = {"xiangqi", "jieqi"}

    def __init__(self, path: Path | str | None = None, nnue: Path | str | None = None):
        self.path = Path(path or PIKAFISH_BIN)
        self.nnue = Path(nnue or PIKAFISH_NNUE)
        self._uci: UCIEngine | None = None
        self._fallback = HeuristicEngine()
        self._jieqi = JieqiSearchEngine()

    def available(self) -> bool:
        return self.path.is_file() and os_access_ok(self.path)

    def _engine(self) -> UCIEngine:
        if self._uci is None or not self._uci.alive:
            nnue = self.nnue if self.nnue.is_file() else None
            self._uci = UCIEngine(
                self.path,
                eval_file=nnue,
                threads=ENGINE_THREADS,
                hash_mb=ENGINE_HASH_MB,
                name="pikafish",
            )
        return self._uci

    def close(self) -> None:
        if self._uci:
            self._uci.quit()
            self._uci = None

    def choose_move(self, req: MoveRequest) -> MoveResponse:
        legal = set(req.legal_moves)
        if not legal:
            return MoveResponse(move="", engine=self.id, comment="无合法走法")
        level = clamp_level(req.level or 5)
        if level == 99:
            level = 10
        depth = XIANGQI_DEPTH[level]
        movetime = XIANGQI_MOVETIME_MS[level]
        fen = req.fen
        extra = req.extra or {}
        game = extra.get("game")
        if req.mode == "jieqi":
            hint = None
            if extra.get("behavior_fen"):
                fen = extra["behavior_fen"]
            elif game is not None and hasattr(game, "behavior_fen"):
                fen = game.behavior_fen()
            # 开局几步局面仍接近标准象棋，用皮卡鱼给根着提示
            ply = getattr(game, "ply", 99) if game is not None else 99
            if level >= 4 and ply <= 8:
                try:
                    eng = self._engine()
                    probe_depth = 8 if level >= 7 else (6 if level >= 5 else 4)
                    hint, _ = eng.best_move(
                        fen,
                        depth=probe_depth,
                        searchmoves=list(legal) if len(legal) <= 80 else None,
                        timeout_sec=1.1 if ply <= 2 else 0.7,
                    )
                    if hint not in legal:
                        hint = None
                except Exception:
                    hint = None
            resp = self._jieqi.choose_move(req, hint=hint)
            if hint and resp.move == hint:
                resp.comment = f"皮卡鱼提示 + {resp.comment}"
                resp.engine = self.id
            else:
                resp.engine = self.id
                resp.comment = resp.comment or "揭棋搜索"
            if resp.move in legal:
                return resp
            fb = self._fallback.choose_move(req)
            fb.fallback = True
            fb.comment = "揭棋搜索未返回合法着，启发式兜底"
            return fb
        try:
            eng = self._engine()
            mv, score = eng.best_move(fen, movetime_ms=movetime if level <= 3 else None, depth=depth)
        except Exception as exc:
            fb = self._fallback.choose_move(req)
            fb.fallback = True
            fb.comment = f"皮卡鱼异常，改用启发式（{exc}）"
            return fb
        if mv in legal:
            return MoveResponse(move=mv, engine=self.id, score=score, raw=mv, comment="皮卡鱼")
        fb = self._fallback.choose_move(req)
        fb.fallback = True
        fb.comment = f"皮卡鱼着法 {mv or '空'} 不合法，改用启发式"
        return fb


def os_access_ok(path: Path) -> bool:
    import os
    return os.access(path, os.X_OK)

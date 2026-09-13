"""用内置搜索当教师，采集比随机自对弈更像棋的样本。"""
from __future__ import annotations

import random

from app.ai.base import MoveRequest
from app.ai.heuristic import HeuristicEngine
from app.ai.jieqi_search import search_jieqi
from app.ai.variant_search import search_variant

_pikafish = None
_heuristic = HeuristicEngine()


def _pk():
    global _pikafish
    if _pikafish is None:
        from app.ai.pikafish import PikafishEngine
        _pikafish = PikafishEngine()
    return _pikafish


def teacher_move(game, legal: list[str], level: int = 2) -> str:
    if not legal:
        return ""
    if legal == ["ready"] or (legal and all(x == "ready" or str(x).startswith("toggle:") for x in legal) and "ready" in legal):
        return "ready"
    mode = getattr(game, "mode", "")
    try:
        if mode == "jieqi":
            mv, _ = search_jieqi(game, legal, level=level, omniscient=False)
            if mv in legal:
                return mv
        elif mode == "xiangqi":
            pk = _pk()
            req = MoveRequest(
                mode="xiangqi",
                fen=game.fen(),
                legal_moves=legal,
                side=game.side,
                level=level,
                extra={"game": game},
            )
            if pk.available():
                resp = pk.choose_move(req)
                if resp.move in legal:
                    return resp.move
            resp = _heuristic.choose_move(req)
            if resp.move in legal:
                return resp.move
        else:
            mv, _, _ = search_variant(game, legal, level)
            if mv in legal:
                return mv
    except Exception:
        pass
    return random.choice(legal)

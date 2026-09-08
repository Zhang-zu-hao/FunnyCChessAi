from __future__ import annotations

import math
import time

from app.catalog import VARIANT_DEPTH, VARIANT_TIME_SEC, clamp_level
from app.game.coords import parse_iccs

from .base import MoveRequest, MoveResponse

VALUE = {
    "K": 10000, "k": 10000, "M": 1400, "m": 1400,
    "R": 1000, "r": 1000, "C": 500, "c": 500, "N": 450, "n": 450,
    "B": 220, "b": 220, "A": 220, "a": 220, "P": 110, "p": 110,
    "X": 180, "x": 180,
}


class _Timeout(Exception):
    pass


def _eval(game, stm: str) -> float:
    if getattr(game, "over", False):
        if game.winner == "draw":
            return 0.0
        return 30_000.0 if game.winner == stm else -30_000.0
    total = 0.0
    for p in game.pieces():
        code = p["code"]
        val = VALUE.get(code, 80)
        sign = 1 if p["color"] == stm else -1
        if p.get("dark"):
            val = 160
        total += sign * val
        if code.upper() == "P":
            total += sign * (p["rank"] if p["color"] == "w" else (9 - p["rank"])) * 4
    if hasattr(game, "in_check") and game.in_check(stm):
        total -= 80
    return total


def _copy(game):
    try:
        return game.copy(search=True)
    except TypeError:
        return game.copy()


def search_variant(game, legal: list[str], level: int) -> tuple[str, float, int]:
    if not legal:
        return "", 0.0, 0
    level = clamp_level(level)
    if level == 99:
        level = 10
    max_d = VARIANT_DEPTH.get(level, 3)
    deadline = time.time() + VARIANT_TIME_SEC.get(level, 1.0)
    jitter = 18 if level <= 3 else 0
    root = _copy(game)
    best_mv, best_sc = legal[0], -math.inf
    nodes = 0

    def neg(g, depth, alpha, beta):
        nonlocal nodes
        nodes += 1
        if time.time() > deadline:
            raise _Timeout()
        if g.over or depth <= 0:
            return _eval(g, g.side)
        moves = g.legal_moves()
        if not moves:
            return _eval(g, g.side)

        def key(m):
            try:
                _ff, _fr, tf, tr = parse_iccs(str(m).split(":")[0])
                grid = getattr(g, "grid", None)
                return 1 if grid is not None and grid[tr][tf] else 0
            except Exception:
                return 0

        moves = sorted(moves, key=key, reverse=True)[:28]
        best = -math.inf
        for mv in moves:
            child = _copy(g)
            try:
                child.apply(mv, validate=False)
            except Exception:
                try:
                    child.apply(mv)
                except Exception:
                    continue
            sc = -neg(child, depth - 1, -beta, -alpha)
            if sc > best:
                best = sc
            if sc > alpha:
                alpha = sc
            if alpha >= beta:
                break
        return best if best != -math.inf else _eval(g, g.side)

    try:
        for depth in range(1, max_d + 1):
            it_best, it_sc = legal[0], -math.inf
            for mv in legal[:40]:
                child = _copy(root)
                try:
                    child.apply(mv, validate=False)
                except Exception:
                    try:
                        child.apply(mv)
                    except Exception:
                        continue
                sc = -neg(child, depth - 1, -math.inf, math.inf)
                if jitter:
                    import random
                    sc += random.random() * jitter
                if sc > it_sc:
                    it_sc, it_best = sc, mv
            best_mv, best_sc = it_best, it_sc
    except _Timeout:
        pass
    return best_mv, best_sc, nodes


class VariantSearchEngine:
    id = "variant-search"
    name = "变体搜索"
    modes = {"anqi", "zhencha", "manchu", "bawang", "wuhu"}

    def available(self) -> bool:
        return True

    def close(self) -> None:
        return None

    def choose_move(self, req: MoveRequest) -> MoveResponse:
        extra = req.extra or {}
        game = extra.get("game")
        legal = list(req.legal_moves)
        if not legal:
            return MoveResponse(move="", engine=self.id, comment="无合法走法")
        if game is None:
            return MoveResponse(move=legal[0], engine=self.id, comment="无局面")
        # 侦查布阵：直接就绪
        if legal == ["ready"] or (legal and all(x == "ready" or x.startswith("toggle:") for x in legal) and "ready" in legal):
            return MoveResponse(move="ready", engine=self.id, comment="完成布阵")
        mv, sc, n = search_variant(game, legal, req.level)
        if mv not in legal:
            mv = legal[0]
        return MoveResponse(move=mv, engine=self.id, score=sc, comment=f"变体搜索 {n} 节点")

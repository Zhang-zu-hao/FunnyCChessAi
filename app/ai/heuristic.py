from __future__ import annotations

import math
import random
from collections import Counter

from app.game.jieqi import JieqiGame
from app.game.xiangqi import XiangqiGame

from .base import MoveRequest, MoveResponse

PIECE_VALUE = {
    "K": 10000, "k": 10000,
    "R": 980, "r": 980,
    "C": 450, "c": 450,
    "N": 400, "n": 400,
    "B": 200, "b": 200,
    "A": 200, "a": 200,
    "P": 100, "p": 100,
}

# 简易位置分：鼓励过河、占中路
CENTER_FILES = {3, 4, 5}


def _side_sign(code: str, side: str) -> int:
    mine = code.isupper() if side == "w" else code.islower()
    return 1 if mine else -1


def _pst(code: str, file: int, rank: int) -> float:
    t = code.upper()
    s = 0.0
    if t == "P":
        if code.isupper():
            s += rank * 8
            if rank >= 5:
                s += 30
        else:
            s += (9 - rank) * 8
            if rank <= 4:
                s += 30
    if t in "NCR" and file in CENTER_FILES:
        s += 6
    if t == "K":
        palace_rank = rank if code.isupper() else 9 - rank
        s += (2 - abs(file - 4)) * 4 - palace_rank
    return s


def eval_xiangqi(game: XiangqiGame, side: str) -> float:
    total = 0.0
    for p in game.pieces():
        code = p["code"]
        total += _side_sign(code, side) * (PIECE_VALUE.get(code, 0) + _pst(code, p["file"], p["rank"]))
    if game.in_check("b" if side == "w" else "w"):
        total += 40
    if game.in_check(side):
        total -= 50
    return total


def eval_jieqi(game: JieqiGame, side: str) -> float:
    total = 0.0
    pools = game.pools
    for p in game.pieces():
        code = p["code"]
        if p["dark"]:
            pool = pools["w" if p["color"] == "w" else "b"]
            n = sum(pool.values()) or 1
            expected = sum(PIECE_VALUE[k] * c for k, c in pool.items()) / n
            total += expected * (1 if p["color"] == side else -1)
        else:
            total += _side_sign(code, side) * (PIECE_VALUE.get(code, 0) + _pst(code, p["file"], p["rank"]))
    if game.in_check("b" if side == "w" else "w"):
        total += 35
    if game.in_check(side):
        total -= 45
    return total


def pick_heuristic(game, legal: list[str], jitter: float = 4.0) -> tuple[str, float]:
    if not legal:
        return "", 0.0
    best_mv, best_sc = legal[0], -math.inf
    for mv in legal:
        g = game.copy() if hasattr(game, "copy") else _clone_xiangqi(game)
        try:
            ev = g.apply(mv)
        except Exception:
            continue
        if g.over and g.winner == (game.side if hasattr(game, "side") else "w"):
            return mv, 1e6
        if hasattr(g, "mode") and g.mode == "jieqi":
            sc = eval_jieqi(g, game.side)
        elif hasattr(g, "pieces") and g.mode != "xiangqi":
            from .variant_search import _eval
            sc = _eval(g, game.side)
        else:
            sc = eval_xiangqi(g, game.side)
        if ev.get("captured"):
            sc += 8
        if ev.get("flip"):
            sc += 3
        sc += random.random() * jitter
        if sc > best_sc:
            best_sc, best_mv = sc, mv
    return best_mv, best_sc


def _clone_xiangqi(game: XiangqiGame) -> XiangqiGame:
    g = XiangqiGame(game.fen())
    g.history = list(game.history)
    g.no_capture = game.no_capture
    g.over = game.over
    g.winner = game.winner
    return g


class HeuristicEngine:
    id = "heuristic"
    name = "内置启发式"
    modes = {"xiangqi", "jieqi"}

    def available(self) -> bool:
        return True

    def close(self) -> None:
        return None

    def choose_move(self, req: MoveRequest) -> MoveResponse:
        extra = req.extra or {}
        game = extra.get("game")
        legal = req.legal_moves
        if not legal:
            return MoveResponse(move="", engine=self.id, comment="无合法走法")
        if game is None:
            return MoveResponse(move=random.choice(legal), engine=self.id, comment="随机", fallback=True)
        mv, sc = pick_heuristic(game, legal)
        if not mv:
            mv = random.choice(legal)
        return MoveResponse(move=mv, engine=self.id, score=sc, comment="启发式搜索")

from __future__ import annotations

import math
import time

from app.catalog import JIEQI_MAX_DEPTH, JIEQI_TIME_SEC, clamp_level
from app.game.coords import parse_iccs
from app.game.jieqi import BLACK, POWS, RED, JieqiGame

from .base import MoveRequest, MoveResponse

VALUE = {
    "K": 100000, "k": 100000,
    "R": 1100, "r": 1100,
    "C": 520, "c": 520,
    "N": 480, "n": 480,
    "B": 230, "b": 230,
    "A": 230, "a": 230,
    "P": 120, "p": 120,
}

CENTER = {2, 3, 4, 5, 6}
MATE = 50_000.0
EXACT, LOWER, UPPER = 0, 1, 2


def _pst(ch: str, file: int, rank: int) -> float:
    t = ch.upper()
    s = 0.0
    if t == "P":
        if ch.isupper():
            s += rank * 12
            if rank >= 5:
                s += 55 + (20 if file in (3, 4, 5) else 0)
        else:
            s += (9 - rank) * 12
            if rank <= 4:
                s += 55 + (20 if file in (3, 4, 5) else 0)
    elif t == "N":
        s += 8 if file in CENTER else 0
        s += 6 if (3 <= rank <= 6) else 0
    elif t == "C":
        s += 10 if file in (3, 4, 5) else 0
    elif t == "R":
        s += 6 if file in (3, 4, 5) else 0
        s += 4 * (rank if ch.isupper() else (9 - rank))
    elif t == "K":
        palace = rank if ch.isupper() else 9 - rank
        s += (2 - abs(file - 4)) * 8 - palace * 3
        if palace >= 1:
            s -= 25
    return s


def _latent(true: str, file: int, rank: int) -> float:
    """暗子尚未按真身走：错位暗子不能按面值满额计算。"""
    beh = POWS.get((file, rank), "P" if true.isupper() else "p").upper()
    tu = true.upper()
    full = VALUE.get(true, 200)
    if tu == beh:
        return full * 0.92 + _pst(true, file, rank)
    if tu in "RC" and beh == "P":
        return 430 + _pst("P" if true.isupper() else "p", file, rank)
    if tu == "N" and beh == "P":
        return 260 + _pst("P" if true.isupper() else "p", file, rank)
    if beh in "RC" and tu == "P":
        return 70
    if beh == "N" and tu == "P":
        return 55
    if tu in "RC":
        return full * 0.68
    if tu == "N":
        return full * 0.75
    if tu in "AB":
        return full * 0.85
    return 0.5 * full + 0.35 * VALUE.get(beh, 150)


def eval_position(game: JieqiGame, omniscient: bool) -> float:
    """行棋方视角。正分 = 轮到走的一方优势。"""
    stm = game.side
    if game.over:
        if game.winner == "draw":
            return 0.0
        return MATE if game.winner == stm else -MATE
    total = 0.0
    ply = game.ply
    for r in range(10):
        for f in range(9):
            ch = game.grid[r][f]
            if not ch:
                continue
            dark = ch in "Xx"
            mine = (ch == "X" or ch.isupper()) == (stm == RED)
            sign = 1.0 if mine else -1.0
            if dark and not omniscient:
                pool = game.pools[RED if ch == "X" else BLACK]
                n = sum(pool.values()) or 1
                expected = sum(VALUE[k] * c for k, c in pool.items()) / n
                total += sign * expected
                continue
            true = game.true_char(f, r) if dark else ch
            if dark:
                val = _latent(true, f, r)
            else:
                val = VALUE.get(true, 0) + _pst(true, f, r)
            if ply < 16 and true.lower() == "k" and abs((r if true.isupper() else 9 - r)) >= 1:
                val -= 40
            total += sign * val
            if omniscient or not dark:
                vu = VALUE.get(true, 0)
                if vu >= 480:
                    opp = BLACK if (true.isupper() or ch == "X") else RED
                    me = RED if opp == BLACK else BLACK
                    if game.attacked_by(f, r, opp):
                        defended = game.attacked_by(f, r, me)
                        total -= sign * vu * (0.62 if not defended else 0.16)
    if game.in_check(stm):
        total -= 110
    if ply < 10:
        # 开局倾向亮马炮车，避免无谓挺兵/动将
        total += 0
    return total


def _cap_val(game: JieqiGame, tf: int, tr: int, omniscient: bool) -> float:
    cap = game.grid[tr][tf]
    if not cap:
        return 0.0
    if cap in "Xx":
        return VALUE.get(game.true_char(tf, tr), 280) if omniscient else 280.0
    return VALUE.get(cap, 200)


def _order(game: JieqiGame, moves: list[str], hint: str | None, omniscient: bool,
           killers: tuple[str, str] | None = None, hist: dict[str, int] | None = None) -> list[str]:
    def key(mv: str) -> float:
        if hint and mv == hint:
            return 20_000.0
        if killers and mv == killers[0]:
            return 8_000.0
        if killers and mv == killers[1]:
            return 7_500.0
        ff, fr, tf, tr = parse_iccs(mv)
        cap = game.grid[tr][tf]
        mover = game.grid[fr][ff]
        s = 0.0
        if cap:
            s += 1_000 + _cap_val(game, tf, tr, omniscient)
            mv_ch = game.true_char(ff, fr) if omniscient else mover
            s -= VALUE.get(mv_ch, 100) * 0.04
        if mover in "Xx":
            true = game.true_char(ff, fr) if omniscient else ""
            tu = true.upper()
            beh = POWS.get((ff, fr), "").upper()
            if tu in "RC":
                s += 140
            elif tu == "N":
                s += 55
            elif tu == "P" and not cap:
                s -= 80
            elif tu in "AB" and not cap:
                s -= 25
            if beh in "RC" and tu == "P":
                s -= 90
            if game.ply < 12 and tu.lower() == "k":
                s -= 200
        else:
            if mover.lower() == "k" and game.ply < 14 and not cap:
                s -= 160
        if tf in (3, 4, 5) and tr in (3, 4, 5, 6):
            s += 6
        if hist:
            s += hist.get(mv, 0) * 0.01
        return s
    return sorted(moves, key=key, reverse=True)


class _Timeout(Exception):
    pass


class _Search:
    def __init__(self, omniscient: bool, deadline: float):
        self.omni = omniscient
        self.deadline = deadline
        self.nodes = 0
        self.tt: dict[int, tuple[int, int, float, str]] = {}
        self.killers: list[list[str]] = [["", ""] for _ in range(64)]
        self.hist: dict[str, int] = {}
        self.best_root = ""
        self.best_sc = -math.inf
        self.completed_depth = 0

    def key(self, game: JieqiGame) -> int:
        items = [game.side, game._ply]
        for r in range(10):
            row = game.grid[r]
            for f in range(9):
                ch = row[f]
                if not ch:
                    continue
                if ch in "Xx" and self.omni:
                    ch = "d" + game.true_char(f, r)
                items.append(ch)
                items.append((f << 4) | r)
        return hash(tuple(items))

    def tick(self) -> None:
        self.nodes += 1
        if (self.nodes & 127) == 0 and time.time() > self.deadline:
            raise _Timeout()

    def negamax(self, game: JieqiGame, depth: int, alpha: float, beta: float,
                ply: int, allow_null: bool) -> float:
        self.tick()
        if game.over:
            return eval_position(game, self.omni)
        orig_alpha = alpha
        k = self.key(game)
        hit = self.tt.get(k)
        if hit and hit[0] >= depth and ply > 0:
            d, flag, sc, _mv = hit
            if flag == EXACT:
                return sc
            if flag == LOWER:
                alpha = max(alpha, sc)
            elif flag == UPPER:
                beta = min(beta, sc)
            if alpha >= beta:
                return sc
        in_chk = game.in_check(game.side)
        if depth <= 0:
            return self.quiesce(game, alpha, beta, 3)
        if in_chk and depth < 12:
            depth += 1
        if (
            allow_null and depth >= 3 and ply > 0 and not in_chk
            and math.isfinite(beta) and beta < 20_000
        ):
            saved = game.side
            game.side = BLACK if saved == RED else RED
            try:
                sc = -self.negamax(game, depth - 3, -beta, -beta + 1, ply + 1, False)
            finally:
                game.side = saved
            if sc >= beta:
                return sc
        moves = game.legal_moves()
        if not moves:
            return -MATE + ply
        tt_mv = hit[3] if hit else None
        kl = tuple(self.killers[ply]) if ply < len(self.killers) else None
        moves = _order(game, moves, tt_mv, self.omni, killers=kl, hist=self.hist)
        best = -math.inf
        best_mv = moves[0]
        for i, mv in enumerate(moves):
            ff, fr, tf, tr = parse_iccs(mv)
            cap = game.grid[tr][tf]
            if ply > 0 and depth <= 2 and i >= 12 + depth * 6 and not cap and not in_chk:
                break
            ev, undo = game.make(mv, record=False, detect_stalemate=False)
            try:
                gives_chk = bool(ev.get("check"))
                new_d = depth - 1
                if (
                    i >= 4 and depth >= 3 and not cap and not gives_chk and not in_chk
                    and math.isfinite(alpha)
                ):
                    sc = -self.negamax(game, new_d - 1, -alpha - 1, -alpha, ply + 1, True)
                    if sc > alpha:
                        sc = -self.negamax(game, new_d, -beta, -alpha, ply + 1, True)
                else:
                    sc = -self.negamax(game, new_d, -beta, -alpha, ply + 1, True)
            finally:
                game.unmake(undo)
            if sc > best:
                best, best_mv = sc, mv
            if sc > alpha:
                alpha = sc
            if alpha >= beta:
                if not cap and ply < len(self.killers):
                    klist = self.killers[ply]
                    if klist[0] != mv:
                        klist[1] = klist[0]
                        klist[0] = mv
                    self.hist[mv] = self.hist.get(mv, 0) + depth * depth
                break
        if best == -math.inf:
            best = eval_position(game, self.omni)
        flag = EXACT
        if best <= orig_alpha:
            flag = UPPER
        elif best >= beta:
            flag = LOWER
        self.tt[k] = (depth, flag, best, best_mv)
        return best

    def quiesce(self, game: JieqiGame, alpha: float, beta: float, qdepth: int) -> float:
        self.tick()
        stand = eval_position(game, self.omni)
        if not math.isfinite(alpha):
            alpha = stand
        if not math.isfinite(beta):
            beta = MATE
        if stand >= beta:
            return stand
        best = stand
        if stand > alpha:
            alpha = stand
        if qdepth <= 0 or game.over:
            return best
        moves = game.legal_moves()
        caps = []
        for mv in moves:
            _ff, _fr, tf, tr = parse_iccs(mv)
            if game.grid[tr][tf]:
                caps.append(mv)
        if not caps:
            return best
        caps = _order(game, caps, None, self.omni)[:18]
        for mv in caps:
            _ff, _fr, tf, tr = parse_iccs(mv)
            see = _cap_val(game, tf, tr, self.omni)
            mover = game.grid[_fr][_ff]
            if mover in "Xx" and not self.omni:
                mv_v = 280.0
            else:
                mv_v = VALUE.get(game.true_char(_ff, _fr) if mover in "Xx" else mover, 200)
            if see + 80 < mv_v * 0.35 and see < 400:
                continue
            _ev, undo = game.make(mv, record=False, detect_stalemate=False)
            try:
                sc = -self.quiesce(game, -beta, -alpha, qdepth - 1)
            finally:
                game.unmake(undo)
            if sc >= beta:
                return sc
            if sc > best:
                best = sc
            if sc > alpha:
                alpha = sc
        return best


def search_jieqi(
    game: JieqiGame,
    legal: list[str],
    level: int,
    hint: str | None = None,
    *,
    omniscient: bool | None = None,
) -> tuple[str, float]:
    resp = search_jieqi_ex(game, legal, level, hint=hint, omniscient=omniscient)
    return resp[0], resp[1]


def search_jieqi_ex(
    game: JieqiGame,
    legal: list[str],
    level: int,
    hint: str | None = None,
    *,
    omniscient: bool | None = None,
) -> tuple[str, float, int, int]:
    if not legal:
        return "", 0.0, 0, 0
    level = clamp_level(level or 5)
    if level == 99:
        level = 10
    # 对局与训练默认都不看暗子真身，只用子力池期望；测试/分析可显式打开透视
    if omniscient is None:
        omniscient = False
    max_d = JIEQI_MAX_DEPTH[level]
    deadline = time.time() + JIEQI_TIME_SEC[level]
    ordered = _order(game, list(legal), hint, omniscient)
    best_mv = ordered[0]
    best_sc = -math.inf
    ctx = _Search(omniscient, deadline)
    completed_depth = 0
    try:
        for depth in range(1, max_d + 1):
            iter_best, iter_sc = ordered[0], -math.inf
            alpha, beta = -math.inf, math.inf
            finished_all = True
            searched = 0
            try:
                for mv in ordered:
                    _ev, undo = game.make(mv, record=False, detect_stalemate=False)
                    try:
                        sc = -ctx.negamax(game, depth - 1, -beta, -alpha, 1, True)
                    finally:
                        game.unmake(undo)
                    searched += 1
                    if sc > iter_sc:
                        iter_sc, iter_best = sc, mv
                    if sc > alpha:
                        alpha = sc
            except _Timeout:
                finished_all = False
            if finished_all:
                best_mv, best_sc = iter_best, iter_sc
                completed_depth = depth
                ordered = [best_mv] + [m for m in ordered if m != best_mv]
            else:
                if searched >= 1 and iter_sc > -math.inf:
                    best_mv, best_sc = iter_best, iter_sc
                break
    except _Timeout:
        pass
    ctx.completed_depth = completed_depth or ctx.completed_depth
    return best_mv, best_sc, completed_depth, ctx.nodes


class JieqiSearchEngine:
    id = "jieqi-search"
    name = "揭棋搜索"
    modes = {"jieqi"}

    def available(self) -> bool:
        return True

    def close(self) -> None:
        return None

    def choose_move(self, req: MoveRequest, hint: str | None = None) -> MoveResponse:
        extra = req.extra or {}
        game = extra.get("game")
        legal = list(req.legal_moves)
        if not legal:
            return MoveResponse(move="", engine=self.id, comment="无合法走法")
        if game is None or not isinstance(game, JieqiGame):
            from .heuristic import HeuristicEngine
            return HeuristicEngine().choose_move(req)
        root = game.copy(search=True)
        mv, sc, depth, nodes = search_jieqi_ex(root, legal, req.level, hint=hint)
        if mv not in legal:
            mv = legal[0]
        return MoveResponse(
            move=mv,
            engine=self.id,
            score=sc,
            comment=f"揭棋搜索 {depth} 层 / {nodes} 节点",
        )

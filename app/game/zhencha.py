from __future__ import annotations

import random
from collections import Counter
from typing import Any

from .coords import move_iccs, parse_iccs
from .grid_xq import GridXiangqi
from .jieqi import INIT_POOL
from .xq_moves import BLACK, NAMES, RED, START_RANKS, attacked_by, color_of, kings_facing, raw_moves

SIM = "RNCABP"


class ZhenchaGame(GridXiangqi):
    """侦查象棋：布局扣放 + 暗子伪装走法 + 吃暗须猜真。"""

    mode = "zhencha"
    palace_strict = True

    def __init__(self, seed: int | None = None):
        super().__init__(START_RANKS)
        rng = random.Random(seed)
        self._truth: dict[tuple[int, int], str] = {}
        for color, upper in ((RED, True), (BLACK, False)):
            cells = [(f, r) for r in range(10) for f in range(9)
                     if self.grid[r][f] and color_of(self.grid[r][f]) == color and self.grid[r][f].lower() != "k"]
            bag = list("".join(k * v for k, v in INIT_POOL.items()))
            rng.shuffle(bag)
            for (f, r), true in zip(cells, bag):
                if not upper:
                    true = true.lower()
                self.grid[r][f] = "X" if upper else "x"
                self._truth[(f, r)] = true
        self.pools = {RED: Counter(INIT_POOL), BLACK: Counter(INIT_POOL)}
        self.last_sim: dict[tuple[int, int], str] = {}
        self.ready = {RED: False, BLACK: False}
        self.phase = "setup"
        self.actions_left = 1

    def copy(self, *, search: bool = False) -> ZhenchaGame:
        g = super().copy(search=search)
        g._truth = dict(self._truth)
        g.pools = {RED: Counter(self.pools[RED]), BLACK: Counter(self.pools[BLACK])}
        g.last_sim = dict(self.last_sim)
        g.ready = dict(self.ready)
        g.phase = self.phase
        return g

    def true_char(self, f: int, r: int) -> str:
        ch = self.grid[r][f]
        if ch in "Xx":
            return self._truth.get((f, r), "P" if ch == "X" else "p")
        return ch

    def _end_setup_if_ready(self) -> None:
        if self.ready[RED] and self.ready[BLACK]:
            self.phase = "play"
            self.side = RED

    def legal_moves(self) -> list[str]:
        if self.over:
            return []
        if self.phase == "setup":
            if self.ready[self.side]:
                return ["ready"] if not (self.ready[RED] and self.ready[BLACK]) else []
            out = ["ready"]
            for r in range(10):
                for f in range(9):
                    ch = self.grid[r][f]
                    if ch and color_of(ch) == self.side and ch.lower() != "k":
                        out.append(f"toggle:{move_iccs(f, r, f, r)[:2]}")
            return out
        out: list[str] = []
        mine = self.side
        for r in range(10):
            for f in range(9):
                ch = self.grid[r][f]
                if not ch or color_of(ch) != mine:
                    continue
                types = [ch.upper()] if ch not in "Xx" else list(SIM)
                last = self.last_sim.get((f, r))
                dests: dict[tuple[int, int], list[str]] = {}
                for et in types:
                    if ch in "Xx" and last and et != last:
                        # 非吃子仍可改伪装；吃子必须沿用 last（在下面过滤）
                        pass
                    for tf, tr in raw_moves(self.grid, f, r, et, mine, palace_strict=self.palace_strict):
                        dests.setdefault((tf, tr), []).append(et)
                for (tf, tr), ets in dests.items():
                    cap = self.grid[tr][tf]
                    unique_ets = list(dict.fromkeys(ets))
                    if cap and ch in "Xx" and last:
                        unique_ets = [last] if last in unique_ets else []
                    if not unique_ets:
                        continue
                    # 检查自身安全
                    ok = []
                    for et in unique_ets:
                        if self._safe_move(f, r, tf, tr):
                            ok.append(et)
                    if not ok:
                        continue
                    if cap in "Xx":
                        opp = BLACK if mine == RED else RED
                        guesses = [k.lower() for k, c in self.pools[opp].items() if c > 0] or ["p"]
                        for et in ok:
                            for guess in guesses:
                                out.append(f"{move_iccs(f, r, tf, tr)}:{et.lower()}:{guess}")
                    elif ch in "Xx":
                        for et in ok:
                            out.append(f"{move_iccs(f, r, tf, tr)}:{et.lower()}")
                    else:
                        out.append(move_iccs(f, r, tf, tr))
        from .repeat import filter_long_check_moves
        return filter_long_check_moves(self, out)

    def _safe_move(self, ff: int, fr: int, tf: int, tr: int) -> bool:
        me = self.grid[fr][ff]
        cap = self.grid[tr][tf]
        self.grid[tr][tf], self.grid[fr][ff] = me, ""
        kp = (tf, tr) if me.lower() == "k" else self._kings.get(self.side)
        opp = BLACK if self.side == RED else RED
        bad = kp is None or kings_facing(self.grid) or attacked_by(
            self.grid, kp[0], kp[1], opp, palace_strict=True
        )
        self.grid[fr][ff], self.grid[tr][tf] = me, cap
        return not bad

    def apply(self, iccs: str, **kwargs) -> dict[str, Any]:
        if self.over:
            raise ValueError("对局已结束")
        raw = iccs.strip().lower()
        if self.phase == "setup":
            return self._apply_setup(raw)
        parts = raw.split(":")
        mv = parts[0]
        as_type = (kwargs.get("as_type") or (parts[1] if len(parts) > 1 else "")).upper()
        guess = (kwargs.get("guess") or (parts[2] if len(parts) > 2 else "")).upper()
        if kwargs.get("validate", True) and raw not in self.legal_moves() and mv not in {x.split(":")[0] for x in self.legal_moves()}:
            # 允许只传坐标，若唯一合法后缀则补全
            cands = [x for x in self.legal_moves() if x.split(":")[0] == mv]
            if len(cands) == 1:
                raw = cands[0]
                parts = raw.split(":")
                mv, as_type = parts[0], (parts[1].upper() if len(parts) > 1 else as_type)
                guess = parts[2].upper() if len(parts) > 2 else guess
            elif not cands:
                raise ValueError(f"非法走法: {iccs}")
        ff, fr, tf, tr = parse_iccs(mv)
        mover = self.grid[fr][ff]
        cap = self.grid[tr][tf]
        ev: dict[str, Any] = {"move": raw, "captured": None, "flip": None, "check": False, "piece": mover}
        # 猜错自损
        if cap in "Xx":
            true = self._truth.get((tf, tr), "")
            if not guess or guess != true.upper():
                self.grid[fr][ff] = ""
                if mover in "Xx":
                    self._truth.pop((ff, fr), None)
                ev["captured"] = None
                ev["suicide"] = True
                ev["piece"] = mover
                self.last_sim.pop((ff, fr), None)
                self.history.append(ev)
                self.last_event = ev
                self.side = BLACK if self.side == RED else RED
                return ev
            cap_true = self._truth.pop((tf, tr))
            key = cap_true.upper()
            if self.pools[color_of(cap_true)].get(key, 0) > 0:
                self.pools[color_of(cap_true)][key] -= 1
            ev["captured"] = cap_true
            ev["captured_name"] = NAMES.get(cap_true, cap_true)
            cap = cap_true
        placed = mover
        if mover in "Xx":
            true = self._truth.pop((ff, fr), "P" if mover == "X" else "p")
            placed = true
            ev["flip"] = true
            ev["piece"] = true
            key = true.upper()
            if self.pools[color_of(true)].get(key, 0) > 0:
                self.pools[color_of(true)][key] -= 1
            if as_type:
                self.last_sim[(tf, tr)] = as_type
        else:
            self.last_sim.pop((ff, fr), None)
        self.grid[tr][tf] = placed
        self.grid[fr][ff] = ""
        self.last_sim.pop((ff, fr), None)
        if placed.lower() == "k":
            self._kings[color_of(placed)] = (tf, tr)
        if cap and str(cap).lower() == "k":
            self.over, self.winner = True, color_of(placed)
        checking = self.in_check(BLACK if self.side == RED else RED)
        ev["check"] = checking
        self.history.append(ev)
        self.last_event = ev
        if not self.over:
            self.side = BLACK if self.side == RED else RED
            if not self.legal_moves():
                self.over, self.winner = True, color_of(placed)
        return ev

    def _apply_setup(self, raw: str) -> dict[str, Any]:
        if raw == "ready":
            self.ready[self.side] = True
            ev = {"move": "ready", "captured": None, "flip": None, "check": False, "piece": None}
            self.history.append(ev)
            self.last_event = ev
            other = BLACK if self.side == RED else RED
            if not self.ready[other]:
                self.side = other
            self._end_setup_if_ready()
            return ev
        if raw.startswith("toggle:"):
            sq = raw.split(":", 1)[1]
            f, r = parse_iccs(sq + sq)[0], parse_iccs(sq + sq)[1]
            ch = self.grid[r][f]
            if not ch or color_of(ch) != self.side or ch.lower() == "k":
                raise ValueError("不能切换该子")
            if ch in "Xx":
                true = self._truth.pop((f, r))
                self.grid[r][f] = true
                key = true.upper()
                if self.pools[self.side].get(key, 0) > 0:
                    self.pools[self.side][key] -= 1
                ev = {"move": raw, "flip": true, "captured": None, "check": False, "piece": true}
            else:
                # 重新扣上
                self._truth[(f, r)] = ch
                self.grid[r][f] = "X" if self.side == RED else "x"
                key = ch.upper()
                self.pools[self.side][key] = self.pools[self.side].get(key, 0) + 1
                ev = {"move": raw, "flip": None, "captured": None, "check": False, "piece": ch}
            self.history.append(ev)
            self.last_event = ev
            return ev
        raise ValueError(f"非法布阵操作: {raw}")

    def pieces(self, observer: str | None = None) -> list[dict[str, Any]]:
        out = []
        for r in range(10):
            for f in range(9):
                ch = self.grid[r][f]
                if not ch:
                    continue
                dark = ch in "Xx"
                out.append({
                    "file": f, "rank": r, "code": ch, "dark": dark,
                    "name": "暗" if dark else NAMES.get(ch, ch),
                    "color": color_of(ch),
                })
        return out

    def observer_state(self, _for_color: str | None = None) -> dict[str, Any]:
        st = super().observer_state(_for_color)
        st["phase"] = self.phase
        st["pool"] = {"w": dict(self.pools[RED]), "b": dict(self.pools[BLACK])}
        st["hint"] = "布阵：点击己方非将棋子切换明/暗，完成后点「完成布阵」" if self.phase == "setup" else "暗子需选择伪装兵种；吃暗子须猜真身"
        st["ready"] = dict(self.ready)
        st["legal"] = self.legal_moves()
        return st

    def auto_ready_ai(self, color: str) -> None:
        """人机时 AI 方立即确认布阵。"""
        self.ready[color] = True
        self._end_setup_if_ready()
        if self.phase == "setup" and self.side == color:
            other = BLACK if color == RED else RED
            if not self.ready[other]:
                self.side = other

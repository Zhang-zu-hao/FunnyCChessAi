from __future__ import annotations

import random
from typing import Any

from .coords import move_iccs, parse_iccs
from .xq_moves import BLACK, NAMES, RED, color_of

ROWS, COLS = 4, 8
RANK = {"K": 7, "R": 6, "N": 5, "C": 4, "A": 3, "B": 2, "P": 1}
BAG = "KAA BBRRNNCCPPPPP".replace(" ", "")  # 16


class AnqiGame:
    """暗棋 / 翻翻棋：4×8，翻子或走一格。"""

    mode = "anqi"

    def __init__(self, seed: int | None = None):
        rng = random.Random(seed)
        red = list(BAG)
        black = [c.lower() for c in BAG]
        bag = red + black
        rng.shuffle(bag)
        self.grid = [["" for _ in range(COLS)] for _ in range(ROWS)]
        self._truth: dict[tuple[int, int], str] = {}
        i = 0
        for r in range(ROWS):
            for f in range(COLS):
                true = bag[i]
                i += 1
                self.grid[r][f] = "X" if true.isupper() else "x"
                self._truth[(f, r)] = true
        self.side = RED
        self.bound = False
        self.history: list[dict[str, Any]] = []
        self.over = False
        self.winner: str | None = None
        self.last_event: dict[str, Any] | None = None
        self.no_capture = 0

    def copy(self, *, search: bool = False) -> AnqiGame:
        g = AnqiGame.__new__(AnqiGame)
        g.grid = [row[:] for row in self.grid]
        g._truth = dict(self._truth)
        g.side = self.side
        g.bound = self.bound
        g.history = [] if search else list(self.history)
        g.over = self.over
        g.winner = self.winner
        g.last_event = None if search else self.last_event
        g.no_capture = self.no_capture
        return g

    @property
    def ply(self) -> int:
        return len(self.history)

    def fen(self) -> str:
        parts = []
        for r in range(ROWS - 1, -1, -1):
            empty, row = 0, ""
            for f in range(COLS):
                ch = self.grid[r][f]
                if not ch:
                    empty += 1
                    continue
                if empty:
                    row += str(empty)
                    empty = 0
                row += ch
            if empty:
                row += str(empty)
            parts.append(row)
        return f"{'/'.join(parts)} {self.side} {int(self.bound)} {self.ply}"

    def engine_fen(self) -> str:
        return self.fen()

    def true_char(self, f: int, r: int) -> str:
        ch = self.grid[r][f]
        if ch in "Xx":
            return self._truth.get((f, r), "P" if ch == "X" else "p")
        return ch

    def _invert_colors(self) -> None:
        for r in range(ROWS):
            for f in range(COLS):
                ch = self.grid[r][f]
                if ch == "X":
                    self.grid[r][f] = "x"
                elif ch == "x":
                    self.grid[r][f] = "X"
                elif ch:
                    self.grid[r][f] = ch.lower() if ch.isupper() else ch.upper()
        self._truth = {(f, r): (t.lower() if t.isupper() else t.upper()) for (f, r), t in self._truth.items()}

    def _can_eat(self, att: str, vic: str) -> bool:
        a, v = att.upper(), vic.upper()
        if a == "C":
            return True
        if a == "P" and v == "K":
            return True
        if a == "K" and v == "P":
            return False
        return RANK[a] >= RANK[v]

    def legal_moves(self) -> list[str]:
        if self.over:
            return []
        out = []
        if not self.bound:
            for r in range(ROWS):
                for f in range(COLS):
                    if self.grid[r][f] in "Xx":
                        out.append(move_iccs(f, r, f, r))
            return out
        for r in range(ROWS):
            for f in range(COLS):
                ch = self.grid[r][f]
                if ch in "Xx":
                    out.append(move_iccs(f, r, f, r))
                    continue
                if not ch or color_of(ch) != self.side:
                    continue
                et = ch.upper()
                if et == "C":
                    for df, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        tf, tr = f + df, r + dr
                        if 0 <= tf < COLS and 0 <= tr < ROWS and not self.grid[tr][tf]:
                            out.append(move_iccs(f, r, tf, tr))
                        jumped = False
                        ff, rr = f + df, r + dr
                        while 0 <= ff < COLS and 0 <= rr < ROWS:
                            occ = self.grid[rr][ff]
                            if occ:
                                if not jumped:
                                    jumped = True
                                else:
                                    if occ not in "Xx" and color_of(occ) != self.side and self._can_eat(ch, occ):
                                        out.append(move_iccs(f, r, ff, rr))
                                    break
                            ff += df
                            rr += dr
                else:
                    for df, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        tf, tr = f + df, r + dr
                        if not (0 <= tf < COLS and 0 <= tr < ROWS):
                            continue
                        tgt = self.grid[tr][tf]
                        if not tgt:
                            out.append(move_iccs(f, r, tf, tr))
                        elif tgt and tgt not in "Xx" and color_of(tgt) != self.side:
                            if self._can_eat(ch, tgt):
                                out.append(move_iccs(f, r, tf, tr))
        return out

    def in_check(self, color: str | None = None) -> bool:
        return False

    def apply(self, iccs: str, **kwargs) -> dict[str, Any]:
        if self.over:
            raise ValueError("对局已结束")
        iccs = iccs.strip().lower().split(":")[0]
        if kwargs.get("validate", True) and iccs not in self.legal_moves():
            raise ValueError(f"非法走法: {iccs}")
        ff, fr, tf, tr = parse_iccs(iccs)
        ev: dict[str, Any] = {"move": iccs, "captured": None, "flip": None, "check": False, "piece": None}
        if (ff, fr) == (tf, tr):
            true = self._truth.pop((ff, fr), "P")
            self.grid[fr][ff] = true
            ev["flip"] = true
            ev["piece"] = true
            if not self.bound:
                if color_of(true) != RED:
                    self._invert_colors()
                    true = self.grid[fr][ff]
                    ev["flip"] = true
                self.bound = True
            self.no_capture += 1
        else:
            mover = self.grid[fr][ff]
            cap = self.grid[tr][tf]
            if cap in "Xx":
                cap = self._truth.pop((tf, tr), cap)
            self.grid[tr][tf] = mover
            self.grid[fr][ff] = ""
            ev["piece"] = mover
            if cap:
                ev["captured"] = cap
                ev["captured_name"] = NAMES.get(cap, cap)
                self.no_capture = 0
                if cap.lower() == "k":
                    self.over, self.winner = True, self.side
            else:
                self.no_capture += 1
        self.history.append(ev)
        self.last_event = ev
        if not self.over:
            self.side = BLACK if self.side == RED else RED
            if self.bound and not self.legal_moves():
                self.over = True
                self.winner = BLACK if self.side == RED else RED
            elif self._no_pieces(self.side):
                self.over = True
                self.winner = BLACK if self.side == RED else RED
        return ev

    def _no_pieces(self, color: str) -> bool:
        for r in range(ROWS):
            for f in range(COLS):
                ch = self.grid[r][f]
                if not ch:
                    continue
                if ch in "Xx":
                    t = self._truth.get((f, r), "")
                    if t and color_of(t) == color:
                        return False
                elif color_of(ch) == color:
                    return False
        return True

    def pieces(self, observer: str | None = None) -> list[dict[str, Any]]:
        out = []
        for r in range(ROWS):
            for f in range(COLS):
                ch = self.grid[r][f]
                if not ch:
                    continue
                dark = ch in "Xx"
                out.append({
                    "file": f, "rank": r, "code": ch, "dark": dark,
                    "name": "暗" if dark else NAMES.get(ch, ch),
                    "color": RED if (ch == "X" or (ch and ch.isupper())) else BLACK,
                })
        return out

    def observer_state(self, _for_color: str | None = None) -> dict[str, Any]:
        last = self.history[-1]["move"] if self.history else None
        return {
            "mode": self.mode,
            "fen": self.fen(),
            "side": self.side,
            "over": self.over,
            "winner": self.winner,
            "check": False,
            "legal": self.legal_moves(),
            "pieces": self.pieces(),
            "last_move": last,
            "last_event": self.last_event,
            "history": [h["move"] for h in self.history],
            "ply": self.ply,
            "pool": None,
            "names": NAMES,
            "board": {"files": 8, "ranks": 4, "river": False, "palace": False},
            "phase": "play" if self.bound else "first-flip",
            "hint": None if self.bound else "先手翻开一枚棋子，该子颜色归你",
        }

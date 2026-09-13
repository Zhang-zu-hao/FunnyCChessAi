from __future__ import annotations

from typing import Any

from .coords import move_iccs, parse_iccs
from .xq_moves import (
    BLACK,
    COLS,
    NAMES,
    RED,
    ROWS,
    START_RANKS,
    attacked_by,
    color_of,
    kings_facing,
    raw_moves,
)


class GridXiangqi:
    """10×9 标准几何的象棋变体底板（明子）。"""

    mode = "xiangqi"
    palace_strict = True

    def __init__(self, ranks: list[str] | None = None):
        src = ranks or START_RANKS
        self.grid = [["" if ch == "." else ch for ch in row] for row in src]
        self.side = RED
        self.history: list[dict[str, Any]] = []
        self.no_capture = 0
        self.over = False
        self.winner: str | None = None
        self.last_event: dict[str, Any] | None = None
        self.actions_left = 1
        self._refresh_kings()

    def _refresh_kings(self) -> None:
        self._kings: dict[str, tuple[int, int] | None] = {RED: None, BLACK: None}
        for r in range(ROWS):
            for f in range(COLS):
                ch = self.grid[r][f]
                if ch == "K":
                    self._kings[RED] = (f, r)
                elif ch == "k":
                    self._kings[BLACK] = (f, r)

    def extra_type(self) -> dict[tuple[int, int], str]:
        return {}

    def copy(self, *, search: bool = False) -> GridXiangqi:
        g = self.__class__.__new__(self.__class__)
        g.grid = [row[:] for row in self.grid]
        g.side = self.side
        g.history = list(self.history[-16:]) if search else list(self.history)
        g.no_capture = self.no_capture
        g.over = self.over
        g.winner = self.winner
        g.last_event = None if search else self.last_event
        g.actions_left = self.actions_left
        g._kings = dict(self._kings)
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
        return f"{'/'.join(parts)} {self.side} - - {self.no_capture} {self.ply // 2 + 1}"

    def engine_fen(self) -> str:
        return self.fen()

    def _et(self, f: int, r: int) -> str:
        ch = self.grid[r][f]
        return self.extra_type().get((f, r), ch.upper() if ch else "")

    def in_check(self, color: str | None = None) -> bool:
        color = color or self.side
        kp = self._kings.get(color)
        if not kp:
            return False
        opp = BLACK if color == RED else RED
        return attacked_by(self.grid, kp[0], kp[1], opp, palace_strict=self.palace_strict, extra_type=self.extra_type())

    def legal_targets(self, ff: int, fr: int) -> list[tuple[int, int]]:
        me = self.grid[fr][ff]
        if not me or color_of(me) != self.side:
            return []
        mine = self.side
        opp = BLACK if mine == RED else RED
        et = self._et(ff, fr)
        raw = raw_moves(self.grid, ff, fr, et, mine, palace_strict=self.palace_strict)
        kp = self._kings.get(mine)
        safe = []
        for tf, tr in raw:
            cap = self.grid[tr][tf]
            self.grid[tr][tf], self.grid[fr][ff] = me, ""
            kpos = (tf, tr) if me.lower() == "k" else kp
            extra = self.extra_type()
            if me.lower() in "rm" and (ff, fr) in extra:
                extra = {((tf, tr) if k == (ff, fr) else k): v for k, v in extra.items()}
            bad = (
                kpos is None
                or kings_facing(self.grid)
                or attacked_by(self.grid, kpos[0], kpos[1], opp, palace_strict=self.palace_strict, extra_type=extra)
            )
            self.grid[fr][ff], self.grid[tr][tf] = me, cap
            if not bad:
                safe.append((tf, tr))
        return safe

    def legal_moves(self) -> list[str]:
        if self.over:
            return []
        out = []
        for r in range(ROWS):
            for f in range(COLS):
                ch = self.grid[r][f]
                if ch and color_of(ch) == self.side:
                    for tf, tr in self.legal_targets(f, r):
                        out.append(move_iccs(f, r, tf, tr))
        from .repeat import filter_long_check_moves
        return filter_long_check_moves(self, out)

    def _end_turn(self) -> None:
        self.side = BLACK if self.side == RED else RED
        self.actions_left = self.actions_for(self.side)

    def actions_for(self, side: str) -> int:
        return 1

    def after_move_keep_turn(self, mover: str, ff: int, fr: int, tf: int, tr: int) -> bool:
        self.actions_left -= 1
        return self.actions_left > 0 and not self.over

    def apply(self, iccs: str, **kwargs) -> dict[str, Any]:
        if self.over:
            raise ValueError("对局已结束")
        iccs = iccs.strip().lower().split(":")[0]
        if kwargs.get("validate", True) and iccs not in self.legal_moves():
            raise ValueError(f"非法走法: {iccs}")
        ff, fr, tf, tr = parse_iccs(iccs)
        mover = self.grid[fr][ff]
        cap = self.grid[tr][tf]
        self.grid[tr][tf] = mover
        self.grid[fr][ff] = ""
        if mover.lower() == "k":
            self._kings[color_of(mover)] = (tf, tr)
        if cap and cap.lower() == "k":
            self._kings[color_of(cap)] = None
        if cap:
            self.no_capture = 0
        else:
            self.no_capture += 1
        checking = self.in_check(BLACK if color_of(mover) == RED else RED)
        ev = {
            "move": iccs, "captured": cap or None, "flip": None, "check": checking,
            "piece": mover, "captured_name": NAMES.get(cap, cap) if cap else None,
        }
        self.history.append(ev)
        self.last_event = ev
        opp = BLACK if color_of(mover) == RED else RED
        if cap and cap.lower() == "k":
            self.over, self.winner = True, color_of(mover)
        elif self._kings.get(opp) is None:
            self.over, self.winner = True, color_of(mover)
        elif self.no_capture >= 120:
            self.over, self.winner = True, "draw"
        keep = self.after_move_keep_turn(mover, ff, fr, tf, tr)
        if not self.over and not keep:
            self._end_turn()
            if not self.legal_moves():
                self.over, self.winner = True, color_of(mover)
                ev["mate"] = True
        else:
            ev["mate"] = bool(self.over and checking)
        return ev

    def pieces(self, observer: str | None = None) -> list[dict[str, Any]]:
        extra = self.extra_type()
        out = []
        for r in range(ROWS):
            for f in range(COLS):
                ch = self.grid[r][f]
                if not ch:
                    continue
                shown = extra.get((f, r), ch)
                out.append({
                    "file": f, "rank": r, "code": shown, "dark": ch in "Xx",
                    "name": NAMES.get(shown, shown),
                    "color": color_of(ch),
                    "super": shown.upper() == "M",
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
            "check": self.in_check(),
            "legal": self.legal_moves(),
            "pieces": self.pieces(),
            "last_move": last.split(":")[0] if last else None,
            "last_event": self.last_event,
            "history": [h["move"] for h in self.history],
            "ply": self.ply,
            "pool": None,
            "names": NAMES,
            "board": {"files": 9, "ranks": 10, "river": True, "palace": True},
            "actions_left": self.actions_left,
            "phase": "play",
        }

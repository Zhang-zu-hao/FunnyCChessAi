from __future__ import annotations

import random
from collections import Counter
from typing import Any

from .coords import move_iccs, parse_iccs

RED, BLACK = "w", "b"
ROWS, COLS = 10, 9

# rank 0 = 红方底线（ICCS 数字 0），与皮卡鱼/cchess 一致
START_RANKS = [
    "RNBAKABNR",  # 0
    ".........",
    ".C.....C.",
    "P.P.P.P.P",
    ".........",
    ".........",
    "p.p.p.p.p",
    ".c.....c.",
    ".........",
    "rnbakabnr",  # 9
]

POWS: dict[tuple[int, int], str] = {}
for _r, _row in enumerate(START_RANKS):
    for _f, _ch in enumerate(_row):
        if _ch != ".":
            POWS[(_f, _r)] = _ch

INIT_POOL = {"R": 2, "N": 2, "B": 2, "A": 2, "C": 2, "P": 5}

NAMES = {
    "K": "帅", "A": "仕", "B": "相", "N": "马", "R": "车", "C": "炮", "P": "兵",
    "k": "将", "a": "士", "b": "象", "n": "马", "r": "车", "c": "砲", "p": "卒",
    "X": "暗", "x": "暗",
}


def color_of(ch: str) -> str:
    return BLACK if ch.islower() else RED


def in_board(f: int, r: int) -> bool:
    return 0 <= f < COLS and 0 <= r < ROWS


class JieqiGame:
    """揭棋（腾讯天天象棋规则）。

    - 将/帅明放，其余 15 子在己方原位独立洗牌后扣放；
    - 暗子首步按**该格开局占位子**的走法行走，走完立即翻开为预定真身；
    - 翻开后的仕/士可出九宫，相/象可过河；将帅仍限九宫；飞将禁着；
    - 困毙判负；40 回合无吃子判和。
    """

    mode = "jieqi"

    def __init__(self, seed: int | None = None):
        rng = random.Random(seed)
        self.grid = [["" if ch == "." else ch for ch in row] for row in START_RANKS]
        self._truth: dict[tuple[int, int], str] = {}
        for color, upper in ((RED, True), (BLACK, False)):
            cells = [
                (f, r) for (f, r), ch in POWS.items()
                if color_of(ch) == color and ch.lower() != "k"
            ]
            bag = list("".join(k * v for k, v in INIT_POOL.items()))
            rng.shuffle(bag)
            for (f, r), true in zip(cells, bag):
                if not upper:
                    true = true.lower()
                self.grid[r][f] = "X" if upper else "x"
                self._truth[(f, r)] = true
        self.pools = {RED: Counter(INIT_POOL), BLACK: Counter(INIT_POOL)}
        self.side = RED
        self.history: list[dict[str, Any]] = []
        self.no_capture = 0
        self.over = False
        self.winner: str | None = None
        self.last_event: dict[str, Any] | None = None
        self._kings = {RED: (4, 0), BLACK: (4, 9)}
        self._ply = 0

    def copy(self, *, search: bool = False) -> JieqiGame:
        g = JieqiGame.__new__(JieqiGame)
        g.grid = [row[:] for row in self.grid]
        g._truth = dict(self._truth)
        g.pools = {RED: Counter(self.pools[RED]), BLACK: Counter(self.pools[BLACK])}
        g.side = self.side
        g.history = [] if search else list(self.history)
        g.no_capture = self.no_capture
        g.over = self.over
        g.winner = self.winner
        g.last_event = None if search else self.last_event
        g._kings = dict(self._kings)
        g._ply = self._ply
        return g

    def true_char(self, file: int, rank: int) -> str:
        ch = self.grid[rank][file]
        if ch in "Xx":
            return self._truth.get((file, rank), POWS.get((file, rank), "P" if ch == "X" else "p"))
        return ch

    def has_legal_move(self) -> bool:
        mine = self.side
        opp = BLACK if mine == RED else RED
        kp = self._kings.get(mine)
        in_chk = bool(kp) and self.attacked_by(kp[0], kp[1], opp)
        for r in range(ROWS):
            for f in range(COLS):
                ch = self.grid[r][f]
                if ch and color_of(ch) == mine and self.legal_targets(f, r, kp=kp, in_chk=in_chk):
                    return True
        return False

    @property
    def ply(self) -> int:
        return self._ply

    def fen(self) -> str:
        return self.engine_fen()

    def engine_fen(self) -> str:
        parts = []
        for r in range(ROWS - 1, -1, -1):
            empty = 0
            row = ""
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
        pool = []
        for pc in "RNBACP":
            pool.append(f"{pc}{self.pools[RED].get(pc, 0)}")
        for pc in "rnbacp":
            pool.append(f"{pc}{self.pools[BLACK].get(pc.upper(), 0)}")
        return f"{'/'.join(parts)} {self.side} {''.join(pool)} {self.no_capture} {len(self.history) // 2 + 1}"

    def behavior_fen(self) -> str:
        """把暗子替换成开局占位子，得到可供标准皮卡鱼搜索的近似 FEN。"""
        parts = []
        for r in range(ROWS - 1, -1, -1):
            empty = 0
            row = ""
            for f in range(COLS):
                ch = self._behavior_piece(f, r)
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
        return f"{'/'.join(parts)} {self.side} - - {self.no_capture} {len(self.history) // 2 + 1}"

    def _behavior_piece(self, f: int, r: int) -> str:
        ch = self.grid[r][f]
        if not ch:
            return ""
        if ch in "Xx":
            return POWS.get((f, r), "P" if ch == "X" else "p")
        return ch

    def effective_type(self, f: int, r: int) -> str:
        ch = self.grid[r][f]
        if not ch:
            return ""
        if ch in "Xx":
            return POWS.get((f, r), "").upper()
        return ch.upper()

    def _find_king(self, color: str) -> tuple[int, int] | None:
        return self._kings.get(color)

    def _kings_facing(self) -> bool:
        pos = [(f, r) for r in range(ROWS) for f in range(COLS) if self.grid[r][f].lower() == "k"]
        if len(pos) < 2:
            return False
        (f1, r1), (f2, r2) = pos
        if f1 != f2:
            return False
        lo, hi = sorted((r1, r2))
        return not any(self.grid[r][f1] for r in range(lo + 1, hi))

    def attacked_by(self, tf: int, tr: int, color: str) -> bool:
        grid = self.grid
        for df, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            f, r, blockers = tf + df, tr + dr, 0
            while in_board(f, r):
                ch = grid[r][f]
                if ch:
                    if blockers == 0:
                        et = self.effective_type(f, r)
                        if color_of(ch) == color and et in ("R", "K"):
                            return True
                        blockers = 1
                    elif blockers == 1:
                        if color_of(ch) == color and self.effective_type(f, r) == "C":
                            return True
                        break
                    else:
                        break
                f += df
                r += dr
        for df, dr in ((2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)):
            f, r = tf + df, tr + dr
            if not in_board(f, r):
                continue
            ch = grid[r][f]
            if not ch or color_of(ch) != color or self.effective_type(f, r) != "N":
                continue
            if abs(df) == 2:
                leg = (tf + df // 2, tr)
            else:
                leg = (tf, tr + dr // 2)
            if grid[leg[1]][leg[0]] == "":
                return True
        for df, dr in ((2, 2), (2, -2), (-2, 2), (-2, -2)):
            f, r = tf + df, tr + dr
            if not (in_board(f, r) and grid[r][f] and color_of(grid[r][f]) == color
                    and self.effective_type(f, r) == "B"):
                continue
            eye = (tf + df // 2, tr + dr // 2)
            if grid[eye[1]][eye[0]] != "":
                continue
            attacker_dark = grid[r][f] in "Xx"
            if attacker_dark:
                if color == RED and tr > 4:
                    continue
                if color == BLACK and tr < 5:
                    continue
            return True
        for df, dr in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            f, r = tf + df, tr + dr
            if not (in_board(f, r) and grid[r][f] and color_of(grid[r][f]) == color
                    and self.effective_type(f, r) == "A"):
                continue
            attacker_dark = grid[r][f] in "Xx"
            if attacker_dark:
                palace = 3 <= tf <= 5 and ((0 <= tr <= 2) if color == RED else (7 <= tr <= 9))
                if not palace:
                    continue
            return True
        back = -1 if color == RED else 1
        for df, dr in ((0, back), (1, 0), (-1, 0)):
            f, r = tf + df, tr + dr
            if not in_board(f, r):
                continue
            ch = grid[r][f]
            if not ch or color_of(ch) != color or self.effective_type(f, r) != "P":
                continue
            if df != 0:
                crossed = (r >= 5) if color == RED else (r <= 4)
                if not crossed:
                    continue
            return True
        return False

    def legal_targets(
        self,
        ff: int,
        fr: int,
        kp: tuple[int, int] | None = None,
        in_chk: bool | None = None,
    ) -> list[tuple[int, int]]:
        me = self.grid[fr][ff]
        if not me or color_of(me) != self.side:
            return []
        mine = self.side
        grid = self.grid
        opp = BLACK if mine == RED else RED
        if kp is None:
            kp = self._kings.get(mine)
        if in_chk is None:
            in_chk = bool(kp) and self.attacked_by(kp[0], kp[1], opp)

        def passable(tf: int, tr: int) -> bool:
            tgt = grid[tr][tf]
            return (not tgt) or color_of(tgt) != mine

        et = self.effective_type(ff, fr)
        dark = me in "Xx"
        raw: list[tuple[int, int]] = []
        if et == "R":
            for df, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                f, r = ff + df, fr + dr
                while in_board(f, r):
                    if not grid[r][f]:
                        raw.append((f, r))
                    else:
                        if passable(f, r):
                            raw.append((f, r))
                        break
                    f += df
                    r += dr
        elif et == "C":
            for df, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                f, r, jumped = ff + df, fr + dr, False
                while in_board(f, r):
                    if not grid[r][f]:
                        if not jumped:
                            raw.append((f, r))
                    elif not jumped:
                        jumped = True
                    else:
                        if passable(f, r):
                            raw.append((f, r))
                        break
                    f += df
                    r += dr
        elif et == "N":
            for df, dr in ((2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)):
                tf, tr = ff + df, fr + dr
                if not in_board(tf, tr):
                    continue
                leg = (ff + df // 2, fr) if abs(df) == 2 else (ff, fr + dr // 2)
                if grid[leg[1]][leg[0]] == "" and passable(tf, tr):
                    raw.append((tf, tr))
        elif et == "B":
            for df, dr in ((2, 2), (2, -2), (-2, 2), (-2, -2)):
                tf, tr = ff + df, fr + dr
                if not in_board(tf, tr):
                    continue
                if dark:
                    if mine == RED and tr > 4:
                        continue
                    if mine == BLACK and tr < 5:
                        continue
                if grid[fr + dr // 2][ff + df // 2] == "" and passable(tf, tr):
                    raw.append((tf, tr))
        elif et == "A":
            for df, dr in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                tf, tr = ff + df, fr + dr
                if not in_board(tf, tr) or not passable(tf, tr):
                    continue
                if dark:
                    palace = 3 <= tf <= 5 and ((0 <= tr <= 2) if mine == RED else (7 <= tr <= 9))
                    if not palace:
                        continue
                raw.append((tf, tr))
        elif et == "K":
            for df, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                tf, tr = ff + df, fr + dr
                palace = 3 <= tf <= 5 and ((0 <= tr <= 2) if mine == RED else (7 <= tr <= 9))
                if palace and passable(tf, tr):
                    raw.append((tf, tr))
        elif et == "P":
            fwd = 1 if mine == RED else -1
            tr = fr + fwd
            if in_board(ff, tr) and passable(ff, tr):
                raw.append((ff, tr))
            crossed = (fr >= 5) if mine == RED else (fr <= 4)
            if crossed:
                for df in (1, -1):
                    tf = ff + df
                    if in_board(tf, fr) and passable(tf, fr):
                        raw.append((tf, fr))

        safe: list[tuple[int, int]] = []
        king_move = kp is not None and (ff, fr) == kp
        on_king_line = kp is not None and (ff == kp[0] or fr == kp[1])
        near_king_diag = (
            kp is not None and abs(ff - kp[0]) == 1 and abs(fr - kp[1]) == 1
        )
        must_filter = in_chk or king_move or on_king_line or near_king_diag or kp is None
        for tf, tr in raw:
            if not must_filter:
                safe.append((tf, tr))
                continue
            cap = grid[tr][tf]
            grid[tr][tf], grid[fr][ff] = grid[fr][ff], ""
            kpos = (tf, tr) if king_move else kp
            bad = kpos is None or self._kings_facing() or self.attacked_by(kpos[0], kpos[1], opp)
            grid[fr][ff], grid[tr][tf] = grid[tr][tf], cap
            if not bad:
                safe.append((tf, tr))
        return safe

    def legal_moves(self) -> list[str]:
        if self.over:
            return []
        mine = self.side
        opp = BLACK if mine == RED else RED
        kp = self._kings.get(mine)
        in_chk = bool(kp) and self.attacked_by(kp[0], kp[1], opp)
        out = []
        for r in range(ROWS):
            for f in range(COLS):
                ch = self.grid[r][f]
                if ch and color_of(ch) == mine:
                    for tf, tr in self.legal_targets(f, r, kp=kp, in_chk=in_chk):
                        out.append(move_iccs(f, r, tf, tr))
        return out

    def in_check(self, color: str | None = None) -> bool:
        color = color or self.side
        kp = self._find_king(color)
        if kp is None:
            return False
        return self.attacked_by(kp[0], kp[1], BLACK if color == RED else RED)

    def make(self, iccs: str, *, record: bool = False, detect_stalemate: bool = False) -> tuple[dict[str, Any], tuple]:
        """落子；返回 (事件, 撤销包)。搜索请 detect_stalemate=False，用空着法表判困毙。"""
        ff, fr, tf, tr = parse_iccs(iccs)
        mover = self.grid[fr][ff]
        mcolor = color_of(mover)
        cap = self.grid[tr][tf]
        undo = (
            ff, fr, tf, tr, mover, cap,
            self._truth.get((ff, fr)), (ff, fr) in self._truth,
            self._truth.get((tf, tr)), (tf, tr) in self._truth,
            Counter(self.pools[RED]), Counter(self.pools[BLACK]),
            self.side, self.no_capture, self.over, self.winner,
            self._kings.get(RED), self._kings.get(BLACK),
            self.last_event, self._ply,
        )
        ev: dict[str, Any] = {"move": iccs, "captured": None, "flip": None, "captured_name": None, "piece": mover}
        if cap:
            self.no_capture = 0
            if cap in "Xx":
                true = self._truth.pop((tf, tr), None)
                if true:
                    key = true.upper()
                    if self.pools[color_of(true)].get(key, 0) > 0:
                        self.pools[color_of(true)][key] -= 1
                    ev["captured"] = true
                    ev["captured_name"] = NAMES.get(true, true)
                else:
                    ev["captured"] = cap
            else:
                ev["captured"] = cap
                ev["captured_name"] = NAMES.get(cap, cap)
        else:
            self.no_capture += 1

        placed = mover
        if mover in "Xx":
            true = self._truth.pop((ff, fr), POWS.get((ff, fr), "P" if mcolor == RED else "p"))
            if color_of(true) != mcolor:
                true = true.upper() if mcolor == RED else true.lower()
            key = true.upper()
            if self.pools[mcolor].get(key, 0) > 0:
                self.pools[mcolor][key] -= 1
            placed = true
            ev["flip"] = true
            ev["piece"] = true
        self.grid[tr][tf] = placed
        self.grid[fr][ff] = ""
        self._ply += 1
        if mover.lower() == "k":
            self._kings[mcolor] = (tf, tr)
        if cap and cap.lower() == "k":
            self._kings[color_of(cap)] = None  # type: ignore[assignment]
        self.side = BLACK if mcolor == RED else RED
        checking = self.in_check(self.side)
        ev["check"] = checking
        if record:
            self.history.append(ev)
            self.last_event = ev
        kp = self._kings.get(self.side)
        if cap and isinstance(cap, str) and cap.lower() == "k":
            self.over, self.winner = True, mcolor
        elif kp is None:
            self.over, self.winner = True, mcolor
        elif self.no_capture >= 80:
            self.over, self.winner = True, "draw"
        elif detect_stalemate and not self.has_legal_move():
            self.over, self.winner = True, mcolor
        ev["mate"] = bool(self.over and self.winner in (RED, BLACK) and checking)
        return ev, undo

    def unmake(self, undo: tuple) -> None:
        (ff, fr, tf, tr, mover, cap,
         truth_from, had_from, truth_to, had_to,
         pool_w, pool_b, side, no_capture, over, winner,
         king_w, king_b, last_event, ply) = undo
        self.grid[fr][ff] = mover
        self.grid[tr][tf] = cap
        self._ply = ply
        self._truth.pop((ff, fr), None)
        self._truth.pop((tf, tr), None)
        if had_from and truth_from is not None:
            self._truth[(ff, fr)] = truth_from
        if had_to and truth_to is not None:
            self._truth[(tf, tr)] = truth_to
        self.pools[RED] = pool_w
        self.pools[BLACK] = pool_b
        self.side = side
        self.no_capture = no_capture
        self.over = over
        self.winner = winner
        self._kings[RED] = king_w
        self._kings[BLACK] = king_b
        self.last_event = last_event

    def apply(self, iccs: str, *, validate: bool = True) -> dict[str, Any]:
        if self.over:
            raise ValueError("对局已结束")
        iccs = iccs.strip().lower()
        if validate and iccs not in self.legal_moves():
            raise ValueError(f"非法走法: {iccs}")
        ev, _undo = self.make(iccs, record=True, detect_stalemate=True)
        return ev

    def pieces(self, observer: str | None = None) -> list[dict[str, Any]]:
        out = []
        for r in range(ROWS):
            for f in range(COLS):
                ch = self.grid[r][f]
                if not ch:
                    continue
                dark = ch in "Xx"
                shown = ch
                name = NAMES.get(ch, ch)
                if dark:
                    name = "暗"
                out.append({
                    "file": f,
                    "rank": r,
                    "code": shown,
                    "dark": dark,
                    "name": name,
                    "color": RED if (ch.isupper() or ch == "X") else BLACK,
                })
        return out

    def observer_state(self, _for_color: str | None = None) -> dict[str, Any]:
        last = self.history[-1]["move"] if self.history else None
        return {
            "mode": self.mode,
            "fen": self.engine_fen(),
            "behavior_fen": self.behavior_fen(),
            "side": self.side,
            "over": self.over,
            "winner": self.winner,
            "check": self.in_check(),
            "legal": self.legal_moves(),
            "pieces": self.pieces(),
            "last_move": last,
            "last_event": self.last_event,
            "history": [h["move"] for h in self.history],
            "ply": self._ply,
            "pool": {
                "w": dict(self.pools[RED]),
                "b": dict(self.pools[BLACK]),
            },
            "names": NAMES,
            "board": {"files": 9, "ranks": 10, "river": True, "palace": True},
        }

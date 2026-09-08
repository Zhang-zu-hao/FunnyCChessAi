from __future__ import annotations

RED, BLACK = "w", "b"
ROWS, COLS = 10, 9
NAMES = {
    "K": "帅", "A": "仕", "B": "相", "N": "马", "R": "车", "C": "炮", "P": "兵", "M": "满",
    "k": "将", "a": "士", "b": "象", "n": "马", "r": "车", "c": "砲", "p": "卒", "m": "满",
    "X": "暗", "x": "暗",
}
START_RANKS = [
    "RNBAKABNR",
    ".........",
    ".C.....C.",
    "P.P.P.P.P",
    ".........",
    ".........",
    "p.p.p.p.p",
    ".c.....c.",
    ".........",
    "rnbakabnr",
]


def color_of(ch: str) -> str:
    if ch in "Xx":
        return RED if ch == "X" else BLACK
    return BLACK if ch.islower() else RED


def in_board(f: int, r: int, cols: int = COLS, rows: int = ROWS) -> bool:
    return 0 <= f < cols and 0 <= r < rows


def palace(f: int, r: int, color: str) -> bool:
    return 3 <= f <= 5 and ((0 <= r <= 2) if color == RED else (7 <= r <= 9))


def raw_moves(
    grid: list[list[str]],
    ff: int,
    fr: int,
    et: str,
    mine: str,
    *,
    palace_strict: bool = True,
    cols: int = COLS,
    rows: int = ROWS,
) -> list[tuple[int, int]]:
    """伪合法目标格（不含将对面/被将过滤）。et 为大写兵种。"""
    def passable(tf: int, tr: int) -> bool:
        tgt = grid[tr][tf]
        return (not tgt) or color_of(tgt) != mine

    raw: list[tuple[int, int]] = []
    if et == "R":
        for df, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            f, r = ff + df, fr + dr
            while in_board(f, r, cols, rows):
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
            while in_board(f, r, cols, rows):
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
            if not in_board(tf, tr, cols, rows):
                continue
            leg = (ff + df // 2, fr) if abs(df) == 2 else (ff, fr + dr // 2)
            if grid[leg[1]][leg[0]] == "" and passable(tf, tr):
                raw.append((tf, tr))
    elif et == "B":
        for df, dr in ((2, 2), (2, -2), (-2, 2), (-2, -2)):
            tf, tr = ff + df, fr + dr
            if not in_board(tf, tr, cols, rows):
                continue
            if palace_strict:
                if mine == RED and tr > 4:
                    continue
                if mine == BLACK and tr < 5:
                    continue
            if grid[fr + dr // 2][ff + df // 2] == "" and passable(tf, tr):
                raw.append((tf, tr))
    elif et == "A":
        for df, dr in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            tf, tr = ff + df, fr + dr
            if not in_board(tf, tr, cols, rows) or not passable(tf, tr):
                continue
            if palace_strict and not palace(tf, tr, mine):
                continue
            raw.append((tf, tr))
    elif et == "K":
        for df, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            tf, tr = ff + df, fr + dr
            if in_board(tf, tr, cols, rows) and palace(tf, tr, mine) and passable(tf, tr):
                raw.append((tf, tr))
    elif et == "P":
        fwd = 1 if mine == RED else -1
        tr = fr + fwd
        if in_board(ff, tr, cols, rows) and passable(ff, tr):
            raw.append((ff, tr))
        crossed = (fr >= 5) if mine == RED else (fr <= 4)
        if crossed:
            for df in (1, -1):
                tf = ff + df
                if in_board(tf, fr, cols, rows) and passable(tf, fr):
                    raw.append((tf, fr))
    elif et == "M":  # 满洲车：车+马+炮
        seen = set()
        for sub in "RNC":
            for t in raw_moves(grid, ff, fr, sub, mine, palace_strict=palace_strict, cols=cols, rows=rows):
                if t not in seen:
                    seen.add(t)
                    raw.append(t)
    return raw


def kings_facing(grid: list[list[str]], cols: int = COLS, rows: int = ROWS) -> bool:
    pos = [(f, r) for r in range(rows) for f in range(cols) if grid[r][f] and grid[r][f].lower() == "k"]
    if len(pos) < 2:
        return False
    (f1, r1), (f2, r2) = pos
    if f1 != f2:
        return False
    lo, hi = sorted((r1, r2))
    return not any(grid[r][f1] for r in range(lo + 1, hi))


def attacked_by(
    grid: list[list[str]],
    tf: int,
    tr: int,
    color: str,
    *,
    palace_strict: bool = True,
    extra_type: dict[tuple[int, int], str] | None = None,
    cols: int = COLS,
    rows: int = ROWS,
) -> bool:
    """color 方是否攻击 tf,tr。extra_type 可将某格视作满洲车等。"""
    for r in range(rows):
        for f in range(cols):
            ch = grid[r][f]
            if not ch or color_of(ch) != color:
                continue
            et = (extra_type or {}).get((f, r), ch.upper())
            if et == "X":
                continue
            for nf, nr in raw_moves(grid, f, r, et, color, palace_strict=palace_strict, cols=cols, rows=rows):
                if nf == tf and nr == tr:
                    return True
    return False

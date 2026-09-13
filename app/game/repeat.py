"""中国象棋 / 揭棋：禁止长将（来回将军不进子）。"""
from __future__ import annotations

from typing import Any

from .coords import parse_iccs


def _core(mv: str) -> str:
    return (mv or "").split(":")[0].strip().lower()


def _is_reverse(a: str, b: str) -> bool:
    a, b = _core(a), _core(b)
    return len(a) >= 4 and len(b) >= 4 and a[:2] == b[2:4] and a[2:4] == b[:2]


def own_check_streak(history: list[dict[str, Any]]) -> int:
    n = 0
    for i in range(len(history) - 2, -1, -2):
        if history[i].get("check"):
            n += 1
        else:
            break
    return n


def long_check_suspect(history: list[dict[str, Any]], mv: str, *, captured: bool) -> bool:
    """是否像长将：来回将，或连续多次将军还不吃子。"""
    if len(history) < 2:
        return False
    last_own = history[-2]
    core = _core(mv)
    if last_own.get("check") and _is_reverse(last_own.get("move") or "", core):
        return True
    streak = own_check_streak(history)
    if streak >= 3 and not captured:
        return True
    if last_own.get("check"):
        same = 0
        for i in range(len(history) - 2, -1, -2):
            h = history[i]
            if not h.get("check"):
                break
            if _core(h.get("move") or "") == core:
                same += 1
        if same >= 2:
            return True
    return False


def _captures(game: Any, mv: str) -> bool:
    core = _core(mv)
    if len(core) < 4:
        return False
    try:
        _ff, _fr, tf, tr = parse_iccs(core)
    except Exception:
        return False
    grid = getattr(game, "grid", None)
    if grid is not None:
        return bool(grid[tr][tf])
    board = getattr(game, "board", None)
    if board is not None and hasattr(board, "get_fench"):
        return bool(board.get_fench((tf, tr)))
    return False


def probe_check_mate(game: Any, mv: str) -> tuple[bool, bool]:
    if hasattr(game, "make") and hasattr(game, "unmake"):
        try:
            ev, undo = game.make(mv, record=False, detect_stalemate=False)
        except Exception:
            return False, False
        try:
            chk = bool(ev.get("check"))
            if not chk:
                return False, False
            mate = bool(getattr(game, "over", False) and getattr(game, "winner", None) not in (None, "draw"))
            if not mate and hasattr(game, "_raw_legal_moves"):
                mate = not game._raw_legal_moves()
            elif not mate and hasattr(game, "has_legal_move"):
                mate = not game.has_legal_move()
            return True, mate
        finally:
            game.unmake(undo)
    copy = getattr(game, "copy", None)
    if copy is None:
        return False, False
    try:
        g = game.copy()
    except TypeError:
        g = game.copy(search=False)
    try:
        ev = g.apply(mv, validate=False)
    except Exception:
        return False, False
    chk = bool(ev.get("check"))
    mate = bool(ev.get("mate") or (chk and g.over and g.winner not in (None, "draw")))
    return chk, mate


def filter_long_check_moves(game: Any, moves: list[str]) -> list[str]:
    hist = getattr(game, "history", None) or []
    if len(hist) < 2 or not moves:
        return moves
    kept: list[str] = []
    for mv in moves:
        cap = _captures(game, mv)
        if not long_check_suspect(hist, mv, captured=cap):
            kept.append(mv)
            continue
        chk, mate = probe_check_mate(game, mv)
        if mate or not chk:
            kept.append(mv)
    return kept

from __future__ import annotations

FILES = "abcdefghi"
RANKS = "0123456789"


def sq_to_iccs(file: int, rank: int) -> str:
    return f"{FILES[file]}{rank}"


def iccs_to_sq(text: str) -> tuple[int, int]:
    return FILES.index(text[0]), int(text[1])


def parse_iccs(move: str) -> tuple[int, int, int, int]:
    move = (move or "").strip().lower()
    if len(move) != 4 or move[0] not in FILES or move[2] not in FILES:
        raise ValueError(f"非法 ICCS 走法: {move!r}")
    if move[1] not in RANKS or move[3] not in RANKS:
        raise ValueError(f"非法 ICCS 走法: {move!r}")
    return FILES.index(move[0]), int(move[1]), FILES.index(move[2]), int(move[3])


def move_iccs(ff: int, fr: int, tf: int, tr: int) -> str:
    return f"{FILES[ff]}{fr}{FILES[tf]}{tr}"

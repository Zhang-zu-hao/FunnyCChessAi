from __future__ import annotations

from typing import Any

from cchess import ChessBoard, FULL_INIT_FEN
from cchess.common import pos2iccs

from .coords import parse_iccs

RED, BLACK = "w", "b"

NAMES = {
    "K": "帅", "A": "仕", "B": "相", "N": "马", "R": "车", "C": "炮", "P": "兵",
    "k": "将", "a": "士", "b": "象", "n": "马", "r": "车", "c": "砲", "p": "卒",
}


class XiangqiGame:
    """标准中国象棋。规则引擎基于 cchess，对外统一 ICCS。"""

    mode = "xiangqi"

    def __init__(self, fen: str | None = None):
        self.board = ChessBoard(fen or FULL_INIT_FEN)
        self.history: list[dict[str, Any]] = []
        self.no_capture = 0
        self.over = False
        self.winner: str | None = None
        self.last_event: dict[str, Any] | None = None

    @property
    def ply(self) -> int:
        return len(self.history)

    @property
    def side(self) -> str:
        return RED if str(self.board.move_player) == "RED" else BLACK

    def fen(self) -> str:
        full = self.board.to_full_fen() if hasattr(self.board, "to_full_fen") else self.board.to_fen()
        return full

    def engine_fen(self) -> str:
        return self.fen()

    def legal_moves(self) -> list[str]:
        if self.over:
            return []
        out: list[str] = []
        try:
            raw = list(self.board.create_moves())
        except Exception:
            return []
        for mv in raw:
            try:
                if self.board.is_valid_move_t(mv) and not self.board.is_checked_move(mv[0], mv[1]):
                    out.append(pos2iccs(mv[0], mv[1]))
            except Exception:
                continue
        from .repeat import filter_long_check_moves
        return filter_long_check_moves(self, out)

    def copy(self) -> XiangqiGame:
        g = XiangqiGame(self.fen())
        g.history = list(self.history)
        g.no_capture = self.no_capture
        g.over = self.over
        g.winner = self.winner
        g.last_event = self.last_event
        return g

    def in_check(self, color: str | None = None) -> bool:
        color = color or self.side
        try:
            board = self.board.copy()
            mover_is_red = str(board.move_player) == "RED"
            want_red = color != RED  # 让对方成为 move_player 再问 is_checking
            if mover_is_red != want_red:
                board.next_turn()
            return bool(board.is_checking())
        except Exception:
            return False

    def apply(self, iccs: str, **kwargs) -> dict[str, Any]:
        if self.over:
            raise ValueError("对局已结束")
        iccs = iccs.strip().lower()
        if kwargs.get("validate", True) and iccs not in self.legal_moves():
            raise ValueError(f"非法走法: {iccs}")
        ff, fr, tf, tr = parse_iccs(iccs)
        captured = self.board.get_fench((tf, tr))
        mover = self.board.get_fench((ff, fr))
        moved = self.board.move_iccs(iccs)
        if not moved:
            raise ValueError(f"引擎拒绝走法: {iccs}")
        checking = bool(self.board.is_checking())
        mate = bool(self.board.is_checkmate())
        self.board.next_turn()
        if captured:
            self.no_capture = 0
        else:
            self.no_capture += 1
        ev = {
            "move": iccs,
            "captured": captured,
            "flip": None,
            "check": checking,
            "mate": mate,
            "piece": mover,
        }
        self.history.append(ev)
        self.last_event = ev
        if mate or self.board.no_moves():
            self.over = True
            self.winner = RED if self.side == BLACK else BLACK
        elif captured and captured.lower() == "k":
            self.over = True
            self.winner = RED if captured == "k" else BLACK
        elif self.no_capture >= 120:
            self.over = True
            self.winner = "draw"
        return ev

    def pieces(self, observer: str | None = None) -> list[dict[str, Any]]:
        out = []
        for rank in range(10):
            for file in range(9):
                ch = self.board.get_fench((file, rank))
                if not ch:
                    continue
                out.append({
                    "file": file,
                    "rank": rank,
                    "code": ch,
                    "dark": False,
                    "name": NAMES.get(ch, ch),
                    "color": RED if ch.isupper() else BLACK,
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
            "last_move": last,
            "last_event": self.last_event,
            "history": [h["move"] for h in self.history],
            "ply": len(self.history),
            "pool": None,
            "names": NAMES,
            "board": {"files": 9, "ranks": 10, "river": True, "palace": True},
        }

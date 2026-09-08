from __future__ import annotations

from .grid_xq import GridXiangqi
from .xq_moves import BLACK, RED, START_RANKS


def _blank() -> list[str]:
    return ["........." for _ in range(10)]


class ManchuGame(GridXiangqi):
    """满洲Dog棋：红方一枚满洲车（车马炮）+ 仕相兵将。"""

    mode = "manchu"

    def __init__(self, seed: int | None = None):
        rows = list(START_RANKS)
        # 红：去掉双马双炮和右车，左车改为满洲车
        red = list(rows[0])
        red[0] = "M"
        red[1] = "."
        red[7] = "."
        red[8] = "."
        rows[0] = "".join(red)
        rows[2] = "........."
        super().__init__(rows)
        self.actions_left = 1


class BawangGame(GridXiangqi):
    """霸王棋：红方帅+车，每回合两次行动。"""

    mode = "bawang"

    def __init__(self, seed: int | None = None):
        rows = _blank()
        rows[0] = "R...K...."
        rows[9] = START_RANKS[9]
        rows[7] = START_RANKS[7]
        rows[6] = START_RANKS[6]
        super().__init__(rows)
        self.actions_left = 2

    def actions_for(self, side: str) -> int:
        return 2 if side == RED else 1


class WuhuGame(GridXiangqi):
    """五虎棋：红方五兵仕相帅；兵可连动两步。"""

    mode = "wuhu"

    def __init__(self, seed: int | None = None):
        rows = list(START_RANKS)
        red = list(rows[0])
        red[0] = "."
        red[1] = "."
        red[7] = "."
        red[8] = "."
        rows[0] = "".join(red)
        rows[2] = "........."
        super().__init__(rows)
        self.actions_left = 1
        self.combo_pawn = False

    def copy(self, *, search: bool = False) -> WuhuGame:
        g = super().copy(search=search)
        g.combo_pawn = self.combo_pawn
        return g

    def actions_for(self, side: str) -> int:
        return 1

    def legal_moves(self) -> list[str]:
        moves = super().legal_moves()
        if self.side != RED or not self.combo_pawn:
            return moves
        # 第二步必须走兵
        pawn = []
        for mv in moves:
            ff, fr = ord(mv[0]) - 97, int(mv[1])
            if self.grid[fr][ff] == "P":
                pawn.append(mv)
        return pawn

    def after_move_keep_turn(self, mover: str, ff: int, fr: int, tf: int, tr: int) -> bool:
        if self.side != RED or self.over:
            self.combo_pawn = False
            return False
        if not self.combo_pawn and mover == "P":
            self.combo_pawn = True
            if any(self.grid[int(mv[1])][ord(mv[0]) - 97] == "P" for mv in GridXiangqi.legal_moves(self)):
                return True
            self.combo_pawn = False
            return False
        self.combo_pawn = False
        return False

    def _end_turn(self) -> None:
        self.combo_pawn = False
        super()._end_turn()

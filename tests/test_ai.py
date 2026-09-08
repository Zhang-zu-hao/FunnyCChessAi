from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ai.base import MoveRequest
from app.ai.heuristic import HeuristicEngine
from app.config import PIKAFISH_BIN
from app.game.xiangqi import XiangqiGame


class TestHeuristic(unittest.TestCase):
    def test_returns_legal(self):
        g = XiangqiGame()
        legal = g.legal_moves()
        eng = HeuristicEngine()
        resp = eng.choose_move(MoveRequest(
            mode="xiangqi", fen=g.fen(), legal_moves=legal, side="w", extra={"game": g}
        ))
        self.assertIn(resp.move, legal)


class TestJieqiSearch(unittest.TestCase):
    def test_opening_legal_and_develops(self):
        from app.ai.jieqi_search import search_jieqi
        from app.game.jieqi import JieqiGame
        g = JieqiGame(seed=1)
        legal = g.legal_moves()
        mv, sc = search_jieqi(g, legal, level=5)
        self.assertIn(mv, legal)
        self.assertFalse(mv.startswith("e0") or mv.startswith("e9"))



@unittest.skipUnless(PIKAFISH_BIN.is_file(), "皮卡鱼二进制不存在")
class TestPikafish(unittest.TestCase):
    def test_opening_move(self):
        from app.ai.pikafish import PikafishEngine
        g = XiangqiGame()
        legal = g.legal_moves()
        eng = PikafishEngine()
        self.assertTrue(eng.available())
        resp = eng.choose_move(MoveRequest(
            mode="xiangqi", fen=g.fen(), legal_moves=legal, side="w", level=2, extra={"game": g}
        ))
        eng.close()
        self.assertIn(resp.move, legal)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.catalog import clamp_level, list_modes, public_meta
from app.game import create_game


class TestCatalog(unittest.TestCase):
    def test_default_jieqi_first(self):
        modes = list_modes()
        self.assertEqual(modes[0]["id"], "jieqi")
        self.assertEqual(public_meta()["name"], "FunnyAi对弈Of象棋")
        self.assertEqual(public_meta()["title"], "FunnyAi对弈Of象棋 — ZZH")
        self.assertEqual(public_meta()["developer"], "ZZH")
        self.assertEqual(public_meta()["github"], "https://github.com/Zhang-zu-hao/FunnyCChessAi")
        self.assertEqual(clamp_level("zzh"), 99)
        self.assertEqual(clamp_level(12), 10)


class TestVariants(unittest.TestCase):
    def test_anqi_start(self):
        g = create_game("anqi", seed=1)
        self.assertEqual(g.mode, "anqi")
        self.assertEqual(len(g.pieces()), 32)
        self.assertTrue(all(p["dark"] for p in g.pieces()))
        legal = g.legal_moves()
        self.assertEqual(len(legal), 32)
        g.apply(legal[0])
        self.assertTrue(g.bound)
        self.assertEqual(g.side, "b")

    def test_manchu_super_rook(self):
        g = create_game("manchu")
        self.assertTrue(any(p["code"] == "M" for p in g.pieces()))
        legal = g.legal_moves()
        self.assertTrue(legal)
        g.apply(legal[0])
        self.assertEqual(g.side, "b")

    def test_bawang_two_actions(self):
        g = create_game("bawang")
        self.assertEqual(g.actions_left, 2)
        red_moves = g.legal_moves()
        g.apply(red_moves[0])
        self.assertEqual(g.side, "w")
        g.apply(g.legal_moves()[0])
        self.assertEqual(g.side, "b")

    def test_wuhu_pawns(self):
        g = create_game("wuhu")
        self.assertTrue(any(p["code"] == "P" for p in g.pieces()))
        g.apply("a3a4")
        self.assertEqual(g.side, "w")
        self.assertTrue(g.combo_pawn)

    def test_zhencha_setup(self):
        g = create_game("zhencha", seed=3)
        self.assertEqual(g.phase, "setup")
        self.assertIn("ready", g.legal_moves())
        g.auto_ready_ai("w")
        g.auto_ready_ai("b")
        self.assertEqual(g.phase, "play")
        self.assertTrue(g.legal_moves())


if __name__ == "__main__":
    unittest.main()

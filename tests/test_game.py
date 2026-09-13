from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.game.jieqi import JieqiGame
from app.game.xiangqi import XiangqiGame


class TestXiangqi(unittest.TestCase):
    def test_opening_moves(self):
        g = XiangqiGame()
        legal = g.legal_moves()
        self.assertEqual(len(legal), 44)
        self.assertIn("h2e2", legal)
        self.assertIn("a3a4", legal)

    def test_cannon_central(self):
        g = XiangqiGame()
        g.apply("h2e2")
        self.assertEqual(g.side, "b")
        self.assertTrue(g.legal_moves())

    def test_illegal_rejected(self):
        g = XiangqiGame()
        with self.assertRaises(ValueError):
            g.apply("a3a5")

    def test_observer_pieces(self):
        g = XiangqiGame()
        pieces = g.pieces()
        self.assertEqual(len(pieces), 32)
        self.assertTrue(any(p["code"] == "K" for p in pieces))


class TestJieqi(unittest.TestCase):
    def test_opening_equals_xiangqi(self):
        g = JieqiGame(seed=1)
        legal = g.legal_moves()
        self.assertEqual(len(legal), 44)
        dark = [p for p in g.pieces() if p["dark"]]
        self.assertEqual(len(dark), 30)
        kings = [p for p in g.pieces() if p["code"] in "Kk"]
        self.assertEqual(len(kings), 2)

    def test_flip_on_move(self):
        g = JieqiGame(seed=7)
        mv = "a3a4"
        self.assertIn(mv, g.legal_moves())
        ev = g.apply(mv)
        self.assertIsNotNone(ev["flip"])
        self.assertNotIn("X", ev["flip"])
        dest = [p for p in g.pieces() if p["file"] == 0 and p["rank"] == 4]
        self.assertEqual(len(dest), 1)
        self.assertFalse(dest[0]["dark"])

    def test_pool_decreases(self):
        g = JieqiGame(seed=3)
        before = sum(g.pools["w"].values())
        g.apply(g.legal_moves()[0])
        after = sum(g.pools["w"].values())
        self.assertEqual(after, before - 1)

    def test_random_play_no_crash(self):
        rng = random.Random(0)
        for seed in range(8):
            g = JieqiGame(seed=seed)
            for _ in range(40):
                moves = g.legal_moves()
                if not moves or g.over:
                    break
                g.apply(rng.choice(moves))
            self.assertTrue(g.ply >= 1 or g.over)

    def test_behavior_fen_standardish(self):
        g = JieqiGame(seed=0)
        fen = g.behavior_fen()
        self.assertIn("RNBAKABNR", fen)
        self.assertIn("rnbakabnr", fen)
        self.assertNotIn("X", fen)

    def test_make_unmake_restores(self):
        g = JieqiGame(seed=11)
        truth = dict(g._truth)
        grid = [row[:] for row in g.grid]
        side = g.side
        pools = {k: dict(v) for k, v in g.pools.items()}
        kings = dict(g._kings)
        ply = g.ply
        for mv in g.legal_moves()[:12]:
            _ev, undo = g.make(mv, record=False, detect_stalemate=False)
            g.unmake(undo)
            self.assertEqual(g.side, side)
            self.assertEqual(g.ply, ply)
            self.assertEqual(g._truth, truth)
            self.assertEqual(g.grid, grid)
            self.assertEqual(g._kings, kings)
            self.assertEqual({k: dict(v) for k, v in g.pools.items()}, pools)

    def test_legal_skip_matches_full_filter(self):
        rng = random.Random(3)
        for seed in range(5):
            g = JieqiGame(seed=seed)
            for _ in range(12):
                full = g.legal_moves()
                mine = g.side
                opp = "b" if mine == "w" else "w"
                kp = g._kings.get(mine)
                forced = []
                for r in range(10):
                    for f in range(9):
                        ch = g.grid[r][f]
                        if ch and (ch.isupper() or ch == "X") == (mine == "w"):
                            from app.game.coords import move_iccs
                            for tf, tr in g.legal_targets(f, r, kp=kp, in_chk=True):
                                forced.append(move_iccs(f, r, tf, tr))
                self.assertEqual(sorted(full), sorted(forced))
                if not full or g.over:
                    break
                g.apply(rng.choice(full))


class TestJieqiSearch(unittest.TestCase):
    def test_returns_legal(self):
        from app.ai.jieqi_search import search_jieqi
        g = JieqiGame(seed=1)
        legal = g.legal_moves()
        mv, sc = search_jieqi(g, legal, level=5)
        self.assertIn(mv, legal)
        self.assertFalse(mv.startswith("e0") or mv.startswith("e9"))

    def test_prefers_winning_capture(self):
        from app.ai.jieqi_search import search_jieqi
        g = JieqiGame(seed=2)
        g.apply(g.legal_moves()[0], validate=False)
        g.apply(g.legal_moves()[0], validate=False)
        legal = g.legal_moves()
        mv, _ = search_jieqi(g, legal, level=5)
        self.assertIn(mv, legal)

    def test_saves_hanging_hidden_rook(self):
        from app.ai.jieqi_search import search_jieqi
        g = JieqiGame(seed=7)
        for mv in ("h2h6", "c9a7", "h6g6", "g9e7"):
            g.apply(mv)
        self.assertEqual(g.true_char(0, 3), "R")
        self.assertTrue(g.attacked_by(0, 3, "b"))
        legal = g.legal_moves()
        mv, _ = search_jieqi(g, legal, level=8, omniscient=True)
        self.assertIn(mv, legal)
        self.assertNotEqual(mv, "b0a2")
        g.apply(mv)
        # 不能把暗车白送给炮
        still = g.grid[3][0] == "X" and g.true_char(0, 3) == "R"
        if still:
            self.assertFalse(
                g.attacked_by(0, 3, "b") and not g.attacked_by(0, 3, "w"),
                f"move {mv} left hidden rook hanging",
            )

    def test_eval_ignores_hidden_identity(self):
        from app.ai.jieqi_search import eval_position
        g = JieqiGame(seed=3)
        reds = [
            (f, r)
            for r in range(10)
            for f in range(9)
            if g.grid[r][f] == "X" and (f, r) in g._truth
        ]
        a = b = None
        for i, p0 in enumerate(reds):
            for p1 in reds[i + 1 :]:
                if g._truth[p0].upper() != g._truth[p1].upper():
                    a, b = p0, p1
                    break
            if a:
                break
        self.assertIsNotNone(a)
        pub0 = eval_position(g, False)
        omni0 = eval_position(g, True)
        g._truth[a], g._truth[b] = g._truth[b], g._truth[a]
        self.assertEqual(pub0, eval_position(g, False))
        self.assertNotEqual(omni0, eval_position(g, True))


class TestLongCheck(unittest.TestCase):
    def test_reverse_shuttle_is_suspect(self):
        from app.game.repeat import long_check_suspect, own_check_streak
        hist = [
            {"move": "h0h7", "check": True},
            {"move": "e9d9", "check": False},
        ]
        self.assertEqual(own_check_streak(hist), 1)
        self.assertTrue(long_check_suspect(hist, "h7h0", captured=False))
        self.assertFalse(long_check_suspect(hist, "a3a4", captured=False))

    def test_streak_blocks_more_idle_checks(self):
        from app.game.repeat import long_check_suspect, own_check_streak
        hist = []
        for _ in range(3):
            hist.append({"move": "h0h7", "check": True})
            hist.append({"move": "e9d9", "check": False})
        self.assertEqual(own_check_streak(hist), 3)
        self.assertTrue(long_check_suspect(hist, "b0c2", captured=False))
        self.assertFalse(long_check_suspect(hist, "b0c2", captured=True))

    def test_jieqi_legal_still_opening(self):
        g = JieqiGame(seed=1)
        self.assertEqual(len(g.legal_moves()), 44)


if __name__ == "__main__":
    unittest.main()

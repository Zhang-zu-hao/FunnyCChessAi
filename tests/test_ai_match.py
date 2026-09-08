from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.catalog import public_meta
from app.rooms import Client, manager


class DummyWS:
    async def send_text(self, _s):
        return None


class TestAiMatch(unittest.IsolatedAsyncioTestCase):
    async def test_aivsai_both_seats(self):
        client = Client(ws=DummyWS(), client_id="c1", name="裁判")
        room = await manager.create(
            mode="xiangqi",
            color="w",
            vs="aivsai",
            level=3,
            engine_id="auto",
            client=client,
            w_engine="heuristic",
            b_engine="heuristic",
            w_level=2,
            b_level=3,
        )
        self.addCleanup(lambda: manager.rooms.pop(room.id, None))
        self.assertEqual(client.role, "spectator")
        self.assertEqual(room.seats["w"].kind, "ai")
        self.assertEqual(room.seats["b"].kind, "ai")
        self.assertEqual(room.seats["w"].engine_id, "heuristic")
        self.assertEqual(room.seats["b"].level, 3)
        snap = manager.snapshot(room)
        self.assertEqual(snap["seats"]["w"]["kind"], "ai")
        self.assertTrue(snap["engines"])

    def test_title(self):
        self.assertIn("ZZH", public_meta()["title"])
        self.assertEqual(public_meta()["name"], "FunnyAi对弈Of象棋")


if __name__ == "__main__":
    unittest.main()

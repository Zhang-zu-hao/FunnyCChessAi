from __future__ import annotations

from .anqi import AnqiGame
from .imbalance import BawangGame, ManchuGame, WuhuGame
from .jieqi import JieqiGame
from .xiangqi import XiangqiGame
from .zhencha import ZhenchaGame

_ALIASES = {
    "jieqi": JieqiGame,
    "揭棋": JieqiGame,
    "xiangqi": XiangqiGame,
    "中国象棋": XiangqiGame,
    "chess": XiangqiGame,
    "anqi": AnqiGame,
    "暗棋": AnqiGame,
    "banqi": AnqiGame,
    "zhencha": ZhenchaGame,
    "侦查": ZhenchaGame,
    "侦查象棋": ZhenchaGame,
    "manchu": ManchuGame,
    "满洲": ManchuGame,
    "满洲dog棋": ManchuGame,
    "bawang": BawangGame,
    "霸王棋": BawangGame,
    "wuhu": WuhuGame,
    "五虎棋": WuhuGame,
}


def create_game(mode: str, seed: int | None = None):
    key = (mode or "jieqi").lower()
    cls = _ALIASES.get(key) or JieqiGame
    try:
        return cls(seed=seed)
    except TypeError:
        return cls()

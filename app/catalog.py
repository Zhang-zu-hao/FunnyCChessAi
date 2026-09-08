from __future__ import annotations

from typing import Any

DEVELOPER = "ZZH"
PROJECT_NAME = "FunnyCChessAi"
PROJECT_TAGLINE = "一个集中国象棋多种衍生玩法于一体、且内置多种ai引擎及模型的在线对战平台。"
GITHUB_URL = "https://github.com/Zhang-zu-hao/FunnyCChessAi"
LICENSE_NAME = "GPL-3.0"
LICENSE_NOTE = "本项目开源（GPL-3.0），与皮卡鱼、cchess 协议兼容。欢迎学习、对局与二次开发。"

# 大厅默认顺序：揭棋为首选
MODE_ORDER = ["jieqi", "xiangqi", "anqi", "zhencha", "manchu", "bawang", "wuhu"]

LEVEL_LABELS = {
    1: "1 入门",
    2: "2 新手",
    3: "3 业余",
    4: "4 普通",
    5: "5 进阶",
    6: "6 精英",
    7: "7 大师",
    8: "8 特级",
    9: "9 宗师",
    10: "10 极限",
    99: "ZZH",
}


def clamp_level(level: int | str | None) -> int:
    if level in ("zzh", "ZZH", 99, "99"):
        return 99
    try:
        n = int(level or 5)
    except (TypeError, ValueError):
        n = 5
    if n == 99:
        return 99
    return max(1, min(10, n))


# 皮卡鱼（象棋）1–10
XIANGQI_DEPTH = {1: 1, 2: 2, 3: 3, 4: 5, 5: 7, 6: 9, 7: 12, 8: 14, 9: 16, 10: 20, 99: 20}
XIANGQI_MOVETIME_MS = {
    1: 50, 2: 90, 3: 160, 4: 280, 5: 450, 6: 800, 7: 1400, 8: 2200, 9: 3500, 10: 6000, 99: 6000,
}

# 揭棋搜索 1–10（4 级起叠加皮卡鱼开局提示）
JIEQI_MAX_DEPTH = {1: 1, 2: 2, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 7, 9: 8, 10: 8, 99: 8}
JIEQI_TIME_SEC = {
    1: 0.08, 2: 0.18, 3: 0.35, 4: 0.7, 5: 1.1, 6: 1.8, 7: 2.8, 8: 4.0, 9: 5.0, 10: 6.5, 99: 6.5,
}
VARIANT_DEPTH = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 5, 10: 5, 99: 5}
VARIANT_TIME_SEC = {
    1: 0.05, 2: 0.1, 3: 0.2, 4: 0.4, 5: 0.7, 6: 1.1, 7: 1.6, 8: 2.2, 9: 3.0, 10: 4.0, 99: 4.0,
}


def _xq_profile(level: int) -> dict[str, Any]:
    if level <= 3:
        engine, algo = "皮卡鱼（浅层）", "UCI 限制深度的 MINIMAX/αβ"
    elif level <= 6:
        engine, algo = "皮卡鱼（轻量）", "NNUE 评估 + 限制深度"
    elif level <= 9:
        engine, algo = "皮卡鱼（全量）", "NNUE + 标准搜索深度"
    elif level == 10:
        engine, algo = "皮卡鱼（极限）", "深度搜索 + 长思考"
    else:
        engine, algo = "ZZH 引擎", "自研权重 / 自定义模型（未接入时回退极限皮卡鱼）"
    d, t = XIANGQI_DEPTH[level], XIANGQI_MOVETIME_MS[level]
    return {
        "engine": engine,
        "algo": algo,
        "params": f"depth={d} · movetime≈{t}ms",
        "depth": d,
        "movetime_ms": t,
    }


def _jq_profile(level: int) -> dict[str, Any]:
    if level <= 3:
        engine, algo = "揭棋浅层搜索", "浅层 MINIMAX + 随机权重"
        extra = "未知暗子按子力池期望"
    elif level <= 6:
        engine, algo = "皮卡鱼轻量 + 揭棋搜索", "开局皮卡鱼提示 · 揭棋规则树"
        extra = "中高强度参考暗子真身"
    elif level <= 9:
        engine, algo = "皮卡鱼 + 揭棋全量搜索", "开局提示 + 迭代加深 / 静态搜索"
        extra = "全知暗子估值（训练/特级强度）"
    elif level == 10:
        engine, algo = "揭棋极限搜索", "最大深度与时间 · 皮卡鱼开局库提示"
        extra = "最长思考"
    else:
        engine, algo = "ZZH 揭棋引擎", "自研模型（未接入时回退极限搜索）"
        extra = "预留 checkpoint / HTTP"
    return {
        "engine": engine,
        "algo": algo,
        "params": f"深度≤{JIEQI_MAX_DEPTH[level]} · {JIEQI_TIME_SEC[level]}s · {extra}",
        "depth": JIEQI_MAX_DEPTH[level],
        "time_sec": JIEQI_TIME_SEC[level],
    }


def _var_profile(level: int, name: str, algo: str) -> dict[str, Any]:
    if level == 99:
        engine = f"ZZH · {name}"
        algo = "自研模型（未接入时回退最强搜索）"
    elif level <= 3:
        engine = f"{name} · 浅层"
    elif level <= 6:
        engine = f"{name} · 标准"
    else:
        engine = f"{name} · 深度"
    return {
        "engine": engine,
        "algo": algo,
        "params": f"深度≤{VARIANT_DEPTH[level]} · {VARIANT_TIME_SEC[level]}s",
        "depth": VARIANT_DEPTH[level],
        "time_sec": VARIANT_TIME_SEC[level],
    }


MODES: dict[str, dict[str, Any]] = {
    "jieqi": {
        "id": "jieqi",
        "name": "揭棋",
        "short": "默认玩法 · 暗子开局，走子即翻开",
        "group": "core",
        "ready": True,
        "board": {"files": 9, "ranks": 10, "river": True, "palace": True},
        "rules_title": "揭棋规则",
        "rules": [
            "将/帅明放，其余 15 子在己方原位独立洗牌后扣放。",
            "暗子第一步按该格开局占位子的走法走，走完立即翻开预定真身。",
            "翻开后的仕/士可出九宫，相/象可过河；将帅仍限九宫。",
            "飞将（将帅对面无子）为禁着；困毙判负；长时间无吃子判和。",
        ],
        "diagram": "start-dark",
        "ai": "jieqi",
    },
    "xiangqi": {
        "id": "xiangqi",
        "name": "中国象棋",
        "short": "传统明棋 · 皮卡鱼引擎",
        "group": "core",
        "ready": True,
        "board": {"files": 9, "ranks": 10, "river": True, "palace": True},
        "rules_title": "中国象棋",
        "rules": [
            "红先黑后，将帅不能对面，不能送将。",
            "仕限九宫，相不能过河，兵过河后可横走。",
            "吃掉对方将/帅或使其无合法应将则胜。",
        ],
        "diagram": "start-full",
        "ai": "xiangqi",
    },
    "anqi": {
        "id": "anqi",
        "name": "暗棋",
        "short": "半张棋盘 · 翻翻棋 / 盲棋",
        "group": "dark",
        "ready": True,
        "board": {"files": 8, "ranks": 4, "river": False, "palace": False},
        "rules_title": "暗棋（翻翻棋）",
        "rules": [
            "使用 4×8 半张棋盘，32 子全部随机扣放。",
            "每回合：翻开一枚暗子，或走己方已翻开的子。",
            "首翻棋子的颜色归先手；另一色归后手。",
            "子力大小：帅＞车＞马＞炮＞士＞象＞兵。大吃小或平级互吃。",
            "兵可吃帅，帅不能吃兵。炮吃子须隔一子（翻山），平时只走一格。",
            "其余子每步上下左右一格。吃光对方或吃掉对方将/帅获胜。",
        ],
        "diagram": "anqi",
        "ai": "anqi",
    },
    "zhencha": {
        "id": "zhencha",
        "name": "侦查象棋",
        "short": "暗子可伪装走法 · 吃子需猜真身",
        "group": "dark",
        "ready": True,
        "board": {"files": 9, "ranks": 10, "river": True, "palace": True},
        "rules_title": "侦查象棋",
        "rules": [
            "将帅明放。开局双方可自行把其余子扣放或亮出，确认后开局。",
            "暗子可模拟车、马、炮、兵、相、士中任意一种走法。",
            "吃子时必须沿用该暗子上一次模拟的兵种走法。",
            "吃对方暗子须预先声明其真身；猜错则己方棋子自损，对方子留下。",
            "明子按中国象棋常规走（仕限九宫、相不过河）。",
        ],
        "diagram": "start-dark",
        "ai": "zhencha",
    },
    "manchu": {
        "id": "manchu",
        "name": "满洲Dog棋",
        "short": "红方一车兼车马炮 · 以少敌多",
        "group": "imbalance",
        "ready": True,
        "board": {"files": 9, "ranks": 10, "river": True, "palace": True},
        "rules_title": "满洲Dog棋（满洲棋）",
        "rules": [
            "黑方子力全满，按中国象棋走。",
            "红方保留将、双仕、双相、五兵，以及一枚「满洲车」。",
            "满洲车可按车、马或炮三者任意一种方式走子与吃子。",
            "其余红子走法与中国象棋相同。红先。",
        ],
        "diagram": "manchu",
        "ai": "manchu",
    },
    "bawang": {
        "id": "bawang",
        "name": "霸王棋",
        "short": "红方一车每回合可走两步",
        "group": "imbalance",
        "ready": True,
        "board": {"files": 9, "ranks": 10, "river": True, "palace": True},
        "rules_title": "霸王棋",
        "rules": [
            "黑方全子。红方仅留帅与一车。",
            "红方每回合有两次行动：车可连走两步，或帅走一步（耗掉一次行动）。",
            "两步之间若已将死则立即结束。黑方每回合仍只走一步。",
        ],
        "diagram": "bawang",
        "ai": "bawang",
    },
    "wuhu": {
        "id": "wuhu",
        "name": "五虎棋",
        "short": "红方五兵双仕双相，兵可连动",
        "group": "imbalance",
        "ready": True,
        "board": {"files": 9, "ranks": 10, "river": True, "palace": True},
        "rules_title": "五虎棋",
        "rules": [
            "黑方全子。红方保留帅、双仕、双相与五个兵。",
            "红方一回合可选：两个兵各走一次，或同一兵连走两步。",
            "若红方改走帅/仕/相，则该回合只走一步。",
            "兵的走法与中国象棋相同（过河可横）。",
        ],
        "diagram": "wuhu",
        "ai": "wuhu",
    },
}


def mode_info(mode: str) -> dict[str, Any]:
    m = (mode or "jieqi").lower()
    if m not in MODES:
        m = "jieqi"
    return MODES[m]


def list_modes() -> list[dict[str, Any]]:
    return [MODES[k] for k in MODE_ORDER if k in MODES]


def ai_profile(mode: str, level: int) -> dict[str, Any]:
    level = clamp_level(level)
    m = mode_info(mode)
    kind = m.get("ai") or m["id"]
    if kind == "xiangqi":
        prof = _xq_profile(level)
    elif kind == "jieqi":
        prof = _jq_profile(level)
    elif kind == "anqi":
        prof = _var_profile(level, "暗棋 MCTS/αβ", "等级吃子启发式 + 蒙特卡洛/αβ")
    elif kind == "zhencha":
        prof = _var_profile(level, "侦查搜索", "伪装走法搜索 + 吃子猜真")
    else:
        names = {"manchu": "满洲Dog 搜索", "bawang": "霸王棋搜索", "wuhu": "五虎棋搜索"}
        prof = _var_profile(level, names.get(kind, "变体搜索"), "规则树 αβ")
    prof.update({
        "level": level,
        "label": LEVEL_LABELS.get(level, str(level)),
        "mode": m["id"],
        "mode_name": m["name"],
    })
    return prof


def public_meta() -> dict[str, Any]:
    return {
        "name": PROJECT_NAME,
        "tagline": PROJECT_TAGLINE,
        "developer": DEVELOPER,
        "license": LICENSE_NAME,
        "license_note": LICENSE_NOTE,
        "github": GITHUB_URL,
        "default_mode": "jieqi",
        "modes": [
            {
                "id": m["id"],
                "name": m["name"],
                "short": m["short"],
                "group": m["group"],
                "ready": m["ready"],
                "rules_title": m["rules_title"],
                "rules": m["rules"],
                "diagram": m["diagram"],
                "board": m["board"],
            }
            for m in list_modes()
        ],
        "levels": [{"value": k, "label": LEVEL_LABELS[k]} for k in list(range(1, 11)) + [99]],
    }

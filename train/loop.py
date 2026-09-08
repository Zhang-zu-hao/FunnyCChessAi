#!/usr/bin/env python3
"""各玩法：搜索教师自对弈 + 策略/价值训练。自动使用 CUDA。

用法：
  python -m train.loop --mode all --hours 3.5 --teacher-level 2 --epochs 8
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

from app.game import create_game
from train.device import describe, torch_device
from train.infer import encode_game, move_index
from train.net import PolicyNet
from train.teacher import teacher_move

MODES = ["jieqi", "xiangqi", "anqi", "zhencha", "manchu", "bawang", "wuhu"]
# 核心玩法多给时间
SHARE = {
    "jieqi": 0.22,
    "xiangqi": 0.22,
    "anqi": 0.11,
    "zhencha": 0.11,
    "manchu": 0.11,
    "bawang": 0.11,
    "wuhu": 0.12,
}


def selfplay(mode: str, games: int, max_ply: int, teacher_level: int, epsilon: float, deadline: float | None):
    xs, ys, vs = [], [], []
    played = 0
    for gidx in range(games):
        if deadline is not None and time.time() >= deadline:
            break
        game = create_game(mode, seed=gidx + int(time.time()) % 100000)
        if hasattr(game, "auto_ready_ai"):
            game.auto_ready_ai("w")
            game.auto_ready_ai("b")
        traj = []
        for _ in range(max_ply):
            if deadline is not None and time.time() >= deadline:
                break
            if game.over:
                break
            legal = game.legal_moves()
            if not legal:
                break
            x = encode_game(game)
            if random.random() < epsilon:
                mv = random.choice(legal)
            else:
                mv = teacher_move(game, legal, level=teacher_level)
            traj.append((x, move_index(mv), game.side))
            try:
                game.apply(mv, validate=False)
            except TypeError:
                try:
                    game.apply(mv)
                except Exception:
                    break
            except Exception:
                try:
                    game.apply(mv)
                except Exception:
                    break
        z = 0.0
        if game.over and game.winner in ("w", "b"):
            z = 1.0
        for x, idx, side in traj:
            xs.append(x)
            ys.append(idx)
            vs.append(z if side == game.winner else (-z if game.winner in ("w", "b") else 0.0))
        played += 1
        print(f"  selfplay {mode} {played} ply={len(traj)} winner={game.winner}", flush=True)
    if not xs:
        return None, 0
    return (
        torch.stack(xs),
        torch.tensor(ys, dtype=torch.long),
        torch.tensor(vs, dtype=torch.float32).unsqueeze(1),
    ), played


def train_mode(mode: str, games: int, epochs: int, out: Path, teacher_level: int, epsilon: float, budget_sec: float | None):
    device = torch_device()
    print(f"设备 {describe()}  玩法 {mode}  教师等级 {teacher_level}", flush=True)
    t0 = time.time()
    deadline = (t0 + budget_sec) if budget_sec else None
    cap = games if games > 0 else 10_000_000
    data, n_games = selfplay(mode, cap, max_ply=90, teacher_level=teacher_level, epsilon=epsilon, deadline=deadline)
    if data is None:
        print("无样本")
        return
    x, y, v = (t.to(device) for t in data)
    net = PolicyNet().to(device)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    loader = DataLoader(TensorDataset(x, y, v), batch_size=min(128, len(x)), shuffle=True)
    net.train()
    for ep in range(epochs):
        total = 0.0
        for bx, by, bv in loader:
            logits, val = net(bx)
            loss = F.cross_entropy(logits, by) + F.mse_loss(val, bv)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss.detach())
        print(f"  epoch {ep+1}/{epochs} loss={total/len(loader):.4f}", flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": net.state_dict(),
        "mode": mode,
        "arch": "from_to_v1",
        "games": n_games,
        "teacher_level": teacher_level,
    }
    torch.save(payload, out)
    elapsed = time.time() - t0
    print(f"已保存 {out}  games={n_games}  {elapsed:.0f}s  size={out.stat().st_size/1e6:.1f}MB", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", default="jieqi", choices=MODES + ["all"])
    p.add_argument("--games", type=int, default=0, help="每玩法局数上限；0 表示仅受 --hours 限制")
    p.add_argument("--epochs", type=int, default=8)
    p.add_argument("--hours", type=float, default=0.0, help="总墙钟预算（小时），按玩法份额切分")
    p.add_argument("--teacher-level", type=int, default=2)
    p.add_argument("--epsilon", type=float, default=0.08)
    p.add_argument("--out-dir", default=str(ROOT / "engines" / "zzh"))
    args = p.parse_args()
    modes = MODES if args.mode == "all" else [args.mode]
    total_share = sum(SHARE[m] for m in modes)
    for m in modes:
        budget = None
        if args.hours > 0:
            budget = args.hours * 3600.0 * (SHARE[m] / total_share)
        games = args.games if args.games > 0 else (10_000_000 if budget else 64)
        train_mode(
            m,
            games,
            args.epochs,
            Path(args.out_dir) / f"{m}.pt",
            teacher_level=args.teacher_level,
            epsilon=args.epsilon,
            budget_sec=budget,
        )


if __name__ == "__main__":
    main()

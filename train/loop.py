#!/usr/bin/env python3
"""各玩法自对弈 + 策略价值训练。自动使用 CUDA。

用法：
  conda activate xiangqi-grpo   # 需已安装 CUDA 版 PyTorch
  python -m train.loop --mode jieqi --games 200 --epochs 5
"""
from __future__ import annotations

import argparse
import random
import sys
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

MODES = ["jieqi", "xiangqi", "anqi", "zhencha", "manchu", "bawang", "wuhu"]


def selfplay(mode: str, games: int, max_ply: int = 80):
    xs, ys, vs = [], [], []
    for gidx in range(games):
        game = create_game(mode, seed=gidx)
        if hasattr(game, "auto_ready_ai"):
            game.auto_ready_ai("w")
            game.auto_ready_ai("b")
        traj = []
        for _ in range(max_ply):
            if game.over:
                break
            legal = game.legal_moves()
            if not legal:
                break
            x = encode_game(game)
            mv = random.choice(legal[:12] or legal)
            traj.append((x, move_index(mv), game.side))
            try:
                game.apply(mv, validate=False)
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
        print(f"  selfplay {mode} {gidx+1}/{games} ply={len(traj)} winner={game.winner}", flush=True)
    if not xs:
        return None
    return (
        torch.stack(xs),
        torch.tensor(ys, dtype=torch.long),
        torch.tensor(vs, dtype=torch.float32).unsqueeze(1),
    )


def train_mode(mode: str, games: int, epochs: int, out: Path):
    device = torch_device()
    print(f"设备 {describe()}  玩法 {mode}", flush=True)
    data = selfplay(mode, games)
    if data is None:
        print("无样本")
        return
    x, y, v = (t.to(device) for t in data)
    net = PolicyNet().to(device)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    loader = DataLoader(TensorDataset(x, y, v), batch_size=min(64, len(x)), shuffle=True)
    net.train()
    for ep in range(epochs):
        total = 0.0
        for bx, by, bv in loader:
            logits, val = net(bx)
            loss = F.cross_entropy(logits, by) + F.mse_loss(val, bv)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss)
        print(f"  epoch {ep+1}/{epochs} loss={total/len(loader):.4f}", flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model": net.state_dict(), "mode": mode}, out)
    print(f"已保存 {out}", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", default="jieqi", choices=MODES + ["all"])
    p.add_argument("--games", type=int, default=64)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--out-dir", default=str(ROOT / "engines" / "zzh"))
    args = p.parse_args()
    modes = MODES if args.mode == "all" else [args.mode]
    for m in modes:
        train_mode(m, args.games, args.epochs, Path(args.out_dir) / f"{m}.pt")


if __name__ == "__main__":
    main()

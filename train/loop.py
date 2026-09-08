#!/usr/bin/env python3
"""GPU 满载训练：大批次策略自对弈 + AMP 残差网络。

用法：
  python -m train.loop --mode all --hours 3.0 --batch-size 1024 --play-batch 256
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

from app.game import create_game
from train.device import describe, torch_device
from train.infer import encode_game, move_index
from train.net import PolicyNet, build_net

MODES = ["jieqi", "xiangqi", "anqi", "zhencha", "manchu", "bawang", "wuhu"]
SHARE = {
    "jieqi": 0.22,
    "xiangqi": 0.22,
    "anqi": 0.11,
    "zhencha": 0.11,
    "manchu": 0.11,
    "bawang": 0.11,
    "wuhu": 0.12,
}
BUFFER_CAP = 180_000


def _tune_cuda():
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    try:
        torch.set_float32_matmul_precision("high")
    except Exception:
        pass


def _apply(game, mv: str) -> bool:
    for kwargs in ({"validate": False}, {}):
        try:
            game.apply(mv, **kwargs)
            return True
        except TypeError:
            continue
        except Exception:
            return False
    return False


def _new_game(mode: str, seed: int):
    game = create_game(mode, seed=seed)
    if hasattr(game, "auto_ready_ai"):
        game.auto_ready_ai("w")
        game.auto_ready_ai("b")
    return game


def _sample_move(logits_row: torch.Tensor, legal: list[str], temperature: float) -> str:
    if not legal:
        return ""
    idx = torch.tensor([move_index(m) for m in legal], dtype=torch.long)
    scores = logits_row[idx]
    if temperature <= 1e-6:
        return legal[int(torch.argmax(scores).item())]
    probs = torch.softmax(scores / temperature, dim=0)
    j = int(torch.multinomial(probs, 1).item())
    return legal[j]


@torch.no_grad()
def gpu_selfplay(
    mode: str,
    net: PolicyNet,
    device: torch.device,
    n_games: int,
    max_ply: int,
    play_batch: int,
    temperature: float,
    deadline: float | None,
):
    net.eval()
    xs, ys, vs = [], [], []
    seed0 = int(time.time()) % 1_000_000
    pending: list[tuple] = []
    next_i = 0
    finished = 0

    def spawn():
        nonlocal next_i
        if next_i >= n_games:
            return
        g = _new_game(mode, seed0 + next_i)
        pending.append((g, [], 0, g.side))
        next_i += 1

    for _ in range(min(play_batch, n_games)):
        spawn()

    while pending and (deadline is None or time.time() < deadline):
        chunk = pending[:play_batch]
        pending = pending[play_batch:]
        batch = torch.stack([encode_game(g) for g, *_ in chunk]).to(device, non_blocking=True)
        batch = batch.contiguous(memory_format=torch.channels_last)
        with torch.autocast(device_type="cuda", enabled=device.type == "cuda"):
            logits, _ = net(batch)
        logits = logits.float().cpu()
        for i, (game, traj, ply, _side0) in enumerate(chunk):
            if game.over or ply >= max_ply:
                z = 1.0 if game.winner in ("w", "b") else 0.0
                for x, idx, side in traj:
                    xs.append(x)
                    ys.append(idx)
                    vs.append(z if side == game.winner else (-z if z else 0.0))
                finished += 1
                spawn()
                continue
            legal = game.legal_moves()
            if not legal:
                finished += 1
                spawn()
                continue
            x = encode_game(game)
            mv = _sample_move(logits[i], legal, temperature)
            traj.append((x, move_index(mv), game.side))
            if not _apply(game, mv):
                finished += 1
                spawn()
                continue
            pending.append((game, traj, ply + 1, _side0))
        if finished and finished % 64 == 0:
            print(f"  gpu-selfplay {mode} done={finished}/{n_games} live={len(pending)} pos={len(xs)}", flush=True)

    for game, traj, ply, _ in pending:
        z = 1.0 if game.over and game.winner in ("w", "b") else 0.0
        for x, idx, side in traj:
            xs.append(x)
            ys.append(idx)
            vs.append(z if side == game.winner else (-z if z else 0.0))
        finished += 1

    if not xs:
        return None, 0
    print(f"  gpu-selfplay {mode} 局={finished} 样本={len(xs)}", flush=True)
    return (
        torch.stack(xs),
        torch.tensor(ys, dtype=torch.long),
        torch.tensor(vs, dtype=torch.float32).unsqueeze(1),
    ), finished


def _append_buffer(buf, extra, cap: int):
    if extra is None:
        return buf
    if buf is None:
        x, y, v = extra
    else:
        x = torch.cat([buf[0], extra[0]], dim=0)
        y = torch.cat([buf[1], extra[1]], dim=0)
        v = torch.cat([buf[2], extra[2]], dim=0)
    if x.size(0) > cap:
        x, y, v = x[-cap:], y[-cap:], v[-cap:]
    return (x, y, v)


def fit_gpu(net, opt, scaler, buf, device, batch_size: int, deadline: float):
    if buf is None:
        return 0, 0.0
    x, y, v = (t.to(device, non_blocking=True) for t in buf)
    n = x.size(0)
    if n < 32:
        return 0, 0.0
    bs = min(batch_size, n)
    net.train()
    steps = 0
    total = 0.0
    t0 = time.time()
    while time.time() < deadline:
        idx = torch.randint(0, n, (bs,), device=device)
        bx = x.index_select(0, idx).contiguous(memory_format=torch.channels_last)
        by = y.index_select(0, idx)
        bv = v.index_select(0, idx)
        opt.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", enabled=device.type == "cuda"):
            logits, val = net(bx)
            loss = F.cross_entropy(logits, by) + F.mse_loss(val, bv)
        if scaler is not None:
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
        else:
            loss.backward()
            opt.step()
        total += float(loss.detach())
        steps += 1
        if steps % 50 == 0:
            dt = max(time.time() - t0, 1e-6)
            mem = torch.cuda.max_memory_allocated() / 1e9 if device.type == "cuda" else 0
            print(
                f"  gpu-train step={steps} loss={total/steps:.4f} "
                f"{steps*bs/dt:.0f} pos/s  mem={mem:.1f}GB",
                flush=True,
            )
    return steps, (total / steps if steps else 0.0)


def _save(net: PolicyNet, out: Path, mode: str, games: int):
    out.parent.mkdir(parents=True, exist_ok=True)
    cpu = {k: v.detach().float().cpu().half() for k, v in net.state_dict().items()}
    torch.save({"model": cpu, "mode": mode, "arch": "resnet_from_to_v2", "net_cfg": net.cfg(), "games": games}, out)
    print(f"已保存 {out}  games={games}  size={out.stat().st_size/1e6:.1f}MB", flush=True)


def train_mode(mode: str, out: Path, budget_sec: float | None, batch_size: int, play_batch: int, play_games: int):
    device = torch_device()
    _tune_cuda()
    print(f"设备 {describe()}  玩法 {mode}  GPU自对弈+AMP", flush=True)
    t0 = time.time()
    deadline = (t0 + budget_sec) if budget_sec else (t0 + 1800)
    net = build_net().to(device)
    net = net.to(memory_format=torch.channels_last)
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-4)
    scaler = torch.amp.GradScaler("cuda") if device.type == "cuda" else None
    buf = None
    games_total = 0
    cycle = 0
    while time.time() < deadline - 8:
        remain = deadline - time.time()
        sp_sec = min(75.0, max(20.0, remain * 0.22))
        fit_sec = remain - sp_sec
        if fit_sec < 15 and buf is not None:
            fit_gpu(net, opt, scaler, buf, device, batch_size, deadline - 5)
            break
        extra, n = gpu_selfplay(
            mode,
            net,
            device,
            n_games=play_games,
            max_ply=80,
            play_batch=play_batch,
            temperature=0.85,
            deadline=time.time() + sp_sec,
        )
        games_total += n
        buf = _append_buffer(buf, extra, BUFFER_CAP)
        if buf is not None:
            print(f"  buffer={buf[0].size(0)}  cycle={cycle}", flush=True)
            fit_gpu(net, opt, scaler, buf, device, batch_size, time.time() + max(20.0, fit_sec * 0.9))
        cycle += 1
        _save(net, out, mode, games_total)
    if buf is None:
        print("无样本")
        return
    elapsed = time.time() - t0
    print(f"玩法 {mode} 结束  {elapsed:.0f}s  games={games_total}", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", default="jieqi", choices=MODES + ["all"])
    p.add_argument("--hours", type=float, default=3.0)
    p.add_argument("--batch-size", type=int, default=4096)
    p.add_argument("--play-batch", type=int, default=256)
    p.add_argument("--play-games", type=int, default=2048)
    p.add_argument("--out-dir", default=str(ROOT / "engines" / "zzh"))
    args = p.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("需要 CUDA GPU")
    modes = MODES if args.mode == "all" else [args.mode]
    total_share = sum(SHARE[m] for m in modes)
    for m in modes:
        budget = args.hours * 3600.0 * (SHARE[m] / total_share) if args.hours > 0 else 1800.0
        train_mode(m, Path(args.out_dir) / f"{m}.pt", budget, args.batch_size, args.play_batch, args.play_games)


if __name__ == "__main__":
    main()

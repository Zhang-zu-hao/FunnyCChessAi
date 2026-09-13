from __future__ import annotations

from pathlib import Path

import torch

from app.game.coords import parse_iccs
from train.device import torch_device
from train.net import MAX_FILES, MAX_RANKS, N_PIECE, build_net

CODE_INDEX = {
    "": 0,
    "K": 1, "A": 2, "B": 3, "N": 4, "R": 5, "C": 6, "P": 7,
    "k": 8, "a": 9, "b": 10, "n": 11, "r": 12, "c": 13, "p": 14,
    "X": 15, "x": 15, "M": 5, "m": 12,
}


def encode_game(game) -> torch.Tensor:
    t = torch.zeros(N_PIECE, MAX_RANKS, MAX_FILES)
    for p in game.pieces():
        # 暗子只编码为 X，网络看不到预定真身
        ch = "X" if p.get("dark") else p["code"]
        idx = CODE_INDEX.get(ch, 0)
        r, f = p["rank"], p["file"]
        if r < MAX_RANKS and f < MAX_FILES:
            t[idx, r, f] = 1
    if getattr(game, "side", "w") == "w":
        t[16].fill_(1)
    return t


def move_index(mv: str) -> int:
    core = mv.split(":")[0]
    if len(core) < 4 or core == "ready" or core.startswith("toggle"):
        return 0
    ff, fr, tf, tr = parse_iccs(core[:4])
    return ((fr * MAX_FILES + ff) * MAX_RANKS + tr) * MAX_FILES + tf


def policy_move(ckpt: Path, req, device=None) -> str:
    device = device or torch_device()
    blob = torch.load(ckpt, map_location=device, weights_only=False)
    net = build_net(blob if isinstance(blob, dict) else None)
    state = blob["model"] if isinstance(blob, dict) and "model" in blob else blob
    net.load_state_dict({k: v.float() for k, v in state.items()})
    net.to(device).eval()
    game = (req.extra or {}).get("game")
    legal = list(req.legal_moves)
    if not legal:
        return ""
    if game is not None:
        from app.game.repeat import filter_long_check_moves
        filtered = filter_long_check_moves(game, legal)
        if filtered:
            legal = filtered
    x = encode_game(game).unsqueeze(0).to(device)
    with torch.no_grad():
        logits, _ = net(x)
        logits = logits[0].cpu()
    best, best_s = legal[0], -1e9
    for mv in legal:
        s = float(logits[move_index(mv)])
        if s > best_s:
            best, best_s = mv, s
    return best

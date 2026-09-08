from __future__ import annotations

from pathlib import Path

import torch

from app.game.coords import parse_iccs
from train.device import torch_device
from train.net import MAX_FILES, MAX_RANKS, N_PIECE, PolicyNet

CODE_INDEX = {
    "": 0,
    "K": 1, "A": 2, "B": 3, "N": 4, "R": 5, "C": 6, "P": 7,
    "k": 8, "a": 9, "b": 10, "n": 11, "r": 12, "c": 13, "p": 14,
    "X": 15, "x": 15, "M": 5, "m": 12,
}


def encode_game(game) -> torch.Tensor:
    t = torch.zeros(N_PIECE, MAX_RANKS, MAX_FILES)
    for p in game.pieces():
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
    net = PolicyNet()
    blob = torch.load(ckpt, map_location=device, weights_only=False)
    state = blob["model"] if isinstance(blob, dict) and "model" in blob else blob
    net.load_state_dict(state)
    net.to(device).eval()
    game = (req.extra or {}).get("game")
    x = encode_game(game).unsqueeze(0).to(device)
    with torch.no_grad():
        logits, _ = net(x)
        logits = logits[0].cpu()
    best, best_s = req.legal_moves[0], -1e9
    for mv in req.legal_moves:
        s = float(logits[move_index(mv)])
        if s > best_s:
            best, best_s = mv, s
    return best

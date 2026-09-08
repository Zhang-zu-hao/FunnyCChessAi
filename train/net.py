"""残差策略网络：棋盘平面 → from/to 走法分布。训练与自训练推理共用。"""
from __future__ import annotations

import torch
import torch.nn as nn

MAX_FILES, MAX_RANKS = 9, 10
N_SQUARES = MAX_RANKS * MAX_FILES
N_PIECE = 17

DEFAULT_CHANNELS = 256
DEFAULT_BLOCKS = 16


class ResidualBlock(nn.Module):
    def __init__(self, channels: int):
        super().__init__()
        self.c1 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.b1 = nn.BatchNorm2d(channels)
        self.c2 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.b2 = nn.BatchNorm2d(channels)

    def forward(self, x):
        h = torch.relu(self.b1(self.c1(x)))
        h = self.b2(self.c2(h))
        return torch.relu(x + h)


class PolicyNet(nn.Module):
    """16×256 残差塔 + from/to 头。fp16 存盘约 60MB，适合 4090 满载训练。"""

    def __init__(self, channels: int = DEFAULT_CHANNELS, blocks: int = DEFAULT_BLOCKS):
        super().__init__()
        self.channels = channels
        self.blocks = blocks
        self.stem = nn.Sequential(
            nn.Conv2d(N_PIECE, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
        )
        self.tower = nn.Sequential(*[ResidualBlock(channels) for _ in range(blocks)])
        self.from_h = nn.Conv2d(channels, 1, 1)
        self.to_h = nn.Conv2d(channels, 1, 1)
        self.value = nn.Sequential(
            nn.Conv2d(channels, 8, 1),
            nn.ReLU(inplace=True),
            nn.Flatten(),
            nn.Linear(8 * N_SQUARES, 256),
            nn.ReLU(inplace=True),
            nn.Linear(256, 1),
        )

    def forward(self, x):
        h = self.tower(self.stem(x))
        frm = self.from_h(h).flatten(1)
        too = self.to_h(h).flatten(1)
        logits = (frm.unsqueeze(2) + too.unsqueeze(1)).flatten(1)
        val = torch.tanh(self.value(h))
        return logits, val

    def cfg(self) -> dict:
        return {"channels": self.channels, "blocks": self.blocks}


def build_net(blob=None, **kwargs) -> PolicyNet:
    cfg = {"channels": DEFAULT_CHANNELS, "blocks": DEFAULT_BLOCKS}
    if isinstance(blob, dict) and isinstance(blob.get("net_cfg"), dict):
        cfg.update({k: blob["net_cfg"][k] for k in ("channels", "blocks") if k in blob["net_cfg"]})
    cfg.update(kwargs)
    return PolicyNet(**cfg)

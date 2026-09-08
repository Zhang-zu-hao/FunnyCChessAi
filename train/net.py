"""轻量策略网络：棋盘平面 → from/to 分解的走法分布。训练与自训练推理共用。"""
from __future__ import annotations

import torch
import torch.nn as nn

MAX_FILES, MAX_RANKS = 9, 10
N_SQUARES = MAX_RANKS * MAX_FILES  # 90
N_PIECE = 17  # 空 + 12 兵种 + 暗子 + 满洲车映射 + 行棋方平面


class PolicyNet(nn.Module):
    """三层卷积 + from/to 头，参数量约数十万，权重远小于 GitHub 100MB 限制。"""

    def __init__(self, channels: int = 64):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(N_PIECE, channels, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, 3, padding=1),
            nn.ReLU(inplace=True),
        )
        self.from_h = nn.Conv2d(channels, 1, 1)
        self.to_h = nn.Conv2d(channels, 1, 1)
        self.value = nn.Sequential(
            nn.Linear(channels * N_SQUARES, 256),
            nn.ReLU(inplace=True),
            nn.Linear(256, 1),
        )

    def forward(self, x):
        h = self.stem(x)
        frm = self.from_h(h).flatten(1)
        too = self.to_h(h).flatten(1)
        logits = (frm.unsqueeze(2) + too.unsqueeze(1)).flatten(1)
        val = torch.tanh(self.value(h.flatten(1)))
        return logits, val

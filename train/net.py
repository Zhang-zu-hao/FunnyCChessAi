"""轻量策略网络：棋盘平面 → 走法分布。训练与 ZZH 推理共用。"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

MAX_FILES, MAX_RANKS = 9, 10
N_PIECE = 16  # 空 + 12 兵种 + 暗红/暗黑 + 满


class PolicyNet(nn.Module):
    def __init__(self, channels: int = 64):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(N_PIECE, channels, 3, padding=1),
            nn.ReLU(),
            nn.Conv2d(channels, channels, 3, padding=1),
            nn.ReLU(),
        )
        self.policy = nn.Linear(channels * MAX_RANKS * MAX_FILES, MAX_RANKS * MAX_FILES * MAX_RANKS * MAX_FILES)
        self.value = nn.Linear(channels * MAX_RANKS * MAX_FILES, 1)

    def forward(self, x):
        h = self.conv(x).flatten(1)
        return self.policy(h), torch.tanh(self.value(h))

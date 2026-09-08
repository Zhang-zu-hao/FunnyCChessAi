from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class MoveRequest:
    mode: str
    fen: str
    legal_moves: list[str]
    side: str
    level: int = 5
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class MoveResponse:
    move: str
    engine: str
    comment: str = ""
    score: float | None = None
    fallback: bool = False
    raw: str = ""


@runtime_checkable
class AIEngine(Protocol):
    """可插拔 AI：标准象棋 / 揭棋共用此接口。"""

    id: str
    name: str
    modes: set[str]

    def choose_move(self, req: MoveRequest) -> MoveResponse:
        ...

    def available(self) -> bool:
        return True

    def close(self) -> None:
        return None

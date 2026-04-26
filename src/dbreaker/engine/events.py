from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class GameEvent:
    type: str
    turn: int
    player: str | None = None
    action: str | None = None
    target: str | None = None
    card: str | None = None
    result: str | None = None
    reason_summary: str = ""
    debug_reasoning: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def digest(self) -> tuple[str, int, str | None, str | None, str | None, str | None]:
        return (self.type, self.turn, self.player, self.action, self.target, self.card)

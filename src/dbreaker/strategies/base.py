from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from dbreaker.engine.actions import Action
from dbreaker.engine.observation import Observation


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    action: Action
    reason_summary: str
    debug_reasoning: str | None = None


class BaseStrategy(Protocol):
    name: str

    def choose_action(
        self,
        observation: Observation,
        legal_actions: list[Action],
    ) -> StrategyDecision: ...

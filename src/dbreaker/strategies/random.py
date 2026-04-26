from __future__ import annotations

import random

from dbreaker.engine.actions import Action
from dbreaker.engine.observation import Observation
from dbreaker.strategies.base import StrategyDecision


class RandomStrategy:
    name = "random"

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def choose_action(
        self,
        observation: Observation,
        legal_actions: list[Action],
    ) -> StrategyDecision:
        if not legal_actions:
            raise ValueError("legal_actions cannot be empty")
        action = self._rng.choice(legal_actions)
        return StrategyDecision(
            action=action,
            reason_summary=f"{self.name} selected a legal action at turn {observation.turn}.",
        )

from __future__ import annotations

from dbreaker.engine.actions import Action, PlayRent
from dbreaker.engine.observation import Observation
from dbreaker.strategies.base import StrategyDecision
from dbreaker.strategies.heuristic import BasicHeuristicStrategy


class AggressiveStrategy(BasicHeuristicStrategy):
    name = "aggressive"

    def choose_action(
        self,
        observation: Observation,
        legal_actions: list[Action],
    ) -> StrategyDecision:
        for action in legal_actions:
            if isinstance(action, PlayRent):
                return StrategyDecision(
                    action=action, reason_summary="Aggressive strategy chose rent."
                )
        return super().choose_action(observation, legal_actions)

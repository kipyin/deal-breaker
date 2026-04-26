from __future__ import annotations

from dbreaker.engine.actions import Action, BankCard
from dbreaker.engine.observation import Observation
from dbreaker.strategies.base import StrategyDecision
from dbreaker.strategies.heuristic import BasicHeuristicStrategy


class DefensiveStrategy(BasicHeuristicStrategy):
    name = "defensive"

    def choose_action(
        self,
        observation: Observation,
        legal_actions: list[Action],
    ) -> StrategyDecision:
        for action in legal_actions:
            if isinstance(action, BankCard):
                return StrategyDecision(
                    action=action, reason_summary="Defensive strategy built bank."
                )
        return super().choose_action(observation, legal_actions)

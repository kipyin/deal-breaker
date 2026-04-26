from __future__ import annotations

from dbreaker.engine.actions import Action
from dbreaker.engine.observation import Observation
from dbreaker.strategies.base import StrategyDecision
from dbreaker.strategies.set_completion import SetCompletionStrategy


class OmniscientBaselineStrategy(SetCompletionStrategy):
    name = "omniscient"

    def choose_action(
        self,
        observation: Observation,
        legal_actions: list[Action],
    ) -> StrategyDecision:
        decision = super().choose_action(observation, legal_actions)
        return StrategyDecision(
            action=decision.action,
            reason_summary="Omniscient baseline used debug-visible observation.",
            debug_reasoning=f"omniscient={observation.omniscient}",
        )

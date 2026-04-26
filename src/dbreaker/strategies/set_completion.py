from __future__ import annotations

from dbreaker.engine.actions import Action, PlayProperty
from dbreaker.engine.cards import SET_SIZE_BY_COLOR
from dbreaker.engine.observation import Observation
from dbreaker.strategies.base import StrategyDecision
from dbreaker.strategies.heuristic import BasicHeuristicStrategy


class SetCompletionStrategy(BasicHeuristicStrategy):
    name = "set_completion"

    def choose_action(
        self,
        observation: Observation,
        legal_actions: list[Action],
    ) -> StrategyDecision:
        property_actions = [action for action in legal_actions if isinstance(action, PlayProperty)]
        if property_actions:
            action = max(
                property_actions,
                key=lambda item: (
                    len(observation.properties.get(item.color, []))
                    / SET_SIZE_BY_COLOR.get(item.color, 99)
                ),
            )
            return StrategyDecision(
                action=action, reason_summary="Set completion strategy extended set."
            )
        return super().choose_action(observation, legal_actions)

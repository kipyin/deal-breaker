from __future__ import annotations

from dbreaker.engine.actions import (
    Action,
    BankCard,
    DiscardCard,
    EndTurn,
    PayWithAssets,
    PlayProperty,
    RespondJustSayNo,
)
from dbreaker.engine.cards import Card
from dbreaker.engine.observation import Observation
from dbreaker.strategies.base import StrategyDecision


class BasicHeuristicStrategy:
    name = "basic"

    def choose_action(
        self,
        observation: Observation,
        legal_actions: list[Action],
    ) -> StrategyDecision:
        if not legal_actions:
            raise ValueError("legal_actions cannot be empty")
        pending_action = _choose_pending_action(observation, legal_actions)
        if pending_action is not None:
            return StrategyDecision(
                action=pending_action,
                reason_summary=f"{self.name} resolved pending {observation.phase.value} action.",
            )
        discard_action = _choose_discard_action(observation, legal_actions)
        if discard_action is not None:
            return StrategyDecision(
                action=discard_action,
                reason_summary=f"{self.name} discarded the lowest value card.",
            )
        for action_type in (PlayProperty, BankCard, EndTurn):
            for action in legal_actions:
                if isinstance(action, action_type):
                    return StrategyDecision(
                        action=action,
                        reason_summary=f"{self.name} prioritized {action_type.__name__}.",
                    )
        return StrategyDecision(action=legal_actions[0], reason_summary="Fallback legal action.")


def _choose_pending_action(
    observation: Observation, legal_actions: list[Action]
) -> Action | None:
    payment_actions = [action for action in legal_actions if isinstance(action, PayWithAssets)]
    if payment_actions:
        return min(
            payment_actions,
            key=lambda action: (
                _payment_total(observation, action),
                len(action.card_ids),
                action.card_ids,
            ),
        )
    response_actions = [
        action for action in legal_actions if isinstance(action, RespondJustSayNo)
    ]
    if response_actions:
        high_impact = (
            observation.pending is not None
            and (observation.pending.amount >= 5 or observation.pending.kind == "deal_breaker")
        )
        if high_impact:
            for action in response_actions:
                if not action.accept:
                    return action
        return next(action for action in response_actions if action.accept)
    return None


def _choose_discard_action(
    observation: Observation, legal_actions: list[Action]
) -> Action | None:
    discard_actions = [action for action in legal_actions if isinstance(action, DiscardCard)]
    if not discard_actions:
        return None
    return min(
        discard_actions,
        key=lambda action: (_card_value(observation.hand, action.card_id), action.card_id),
    )


def _payment_total(observation: Observation, action: PayWithAssets) -> int:
    return sum(_asset_value(observation, card_id) for card_id in action.card_ids)


def _asset_value(observation: Observation, card_id: str) -> int:
    for card in observation.bank:
        if card.id == card_id:
            return card.value
    for cards in observation.properties.values():
        value = _card_value(cards, card_id)
        if value >= 0:
            return value
    return 0


def _card_value(cards: list[Card], card_id: str) -> int:
    for card in cards:
        if card.id == card_id:
            return card.value
    return -1

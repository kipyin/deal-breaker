"""Fair-information visibility: counts derivable from Observation plus public deck constants."""

from __future__ import annotations

from collections.abc import Iterator

from dbreaker.engine.cards import (
    ACTION_COUNT_BY_SUBTYPE,
    NATURAL_PROPERTY_COUNT_BY_COLOR,
    SET_SIZE_BY_COLOR,
    WILD_PROPERTY_DECK_TOTAL,
    ActionSubtype,
    Card,
    CardKind,
    PropertyColor,
)
from dbreaker.engine.observation import Observation


def iter_visible_cards(observation: Observation) -> Iterator[Card]:
    for card in observation.hand:
        yield card
    for card in observation.bank:
        yield card
    for cards in observation.properties.values():
        for card in cards:
            yield card
    for opp in observation.opponents.values():
        for card in opp.bank:
            yield card
        for cards in opp.properties.values():
            for card in cards:
                yield card


def natural_property_visible_by_color(observation: Observation) -> dict[PropertyColor, int]:
    counts = {color: 0 for color in SET_SIZE_BY_COLOR}
    for card in iter_visible_cards(observation):
        if card.kind == CardKind.PROPERTY and card.color is not None:
            counts[card.color] += 1
    return counts


def wild_property_visible_count(observation: Observation) -> int:
    return sum(1 for card in iter_visible_cards(observation) if card.kind == CardKind.WILD_PROPERTY)


def unseen_natural_property_by_color(observation: Observation) -> dict[PropertyColor, int]:
    visible = natural_property_visible_by_color(observation)
    return {
        color: max(0, NATURAL_PROPERTY_COUNT_BY_COLOR.get(color, 0) - visible[color])
        for color in SET_SIZE_BY_COLOR
    }


def wild_unseen_count(observation: Observation) -> int:
    return max(0, WILD_PROPERTY_DECK_TOTAL - wild_property_visible_count(observation))


def visible_action_subtype_count(observation: Observation, subtype: ActionSubtype) -> int:
    return sum(
        1
        for card in iter_visible_cards(observation)
        if card.kind == CardKind.ACTION and card.action_subtype == subtype
    )


def unseen_action_subtype_count(observation: Observation, subtype: ActionSubtype) -> int:
    cap = ACTION_COUNT_BY_SUBTYPE.get(subtype, 0)
    return max(0, cap - visible_action_subtype_count(observation, subtype))


def hand_attack_steal_counts(observation: Observation) -> tuple[int, int, int]:
    deal_breaker = sly_deal = forced_deal = 0
    for card in observation.hand:
        match card.action_subtype:
            case ActionSubtype.DEAL_BREAKER:
                deal_breaker += 1
            case ActionSubtype.SLY_DEAL:
                sly_deal += 1
            case ActionSubtype.FORCED_DEAL:
                forced_deal += 1
            case _:
                pass
    return deal_breaker, sly_deal, forced_deal

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from dbreaker.engine.actions import (
    Action,
    BankCard,
    DiscardCard,
    DrawCards,
    EndTurn,
    PayWithAssets,
    PlayActionCard,
    PlayProperty,
    PlayRent,
    RearrangeProperty,
    RespondJustSayNo,
)
from dbreaker.engine.cards import (
    SET_SIZE_BY_COLOR,
    ActionSubtype,
    Card,
    CardKind,
    PropertyColor,
)
from dbreaker.engine.observation import Observation
from dbreaker.engine.rules import GamePhase

FEATURE_SCHEMA_VERSION = "dbreaker-ml-features-v1"

_PHASES = tuple(GamePhase)
_CARD_KINDS = tuple(CardKind)
_ACTION_SUBTYPES = tuple(ActionSubtype)
_COLORS = tuple(PropertyColor)
_SET_COLORS = tuple(SET_SIZE_BY_COLOR)
_ACTION_TYPES = (
    DrawCards,
    BankCard,
    PlayProperty,
    PlayRent,
    PlayActionCard,
    PayWithAssets,
    DiscardCard,
    RearrangeProperty,
    EndTurn,
    RespondJustSayNo,
)
_T = TypeVar("_T")

_OBS_NUMERIC_DIM = 16
_CARD_SUMMARY_DIM = len(_CARD_KINDS) + len(_ACTION_SUBTYPES) + len(_COLORS) + 2
_OPPONENT_SUMMARY_DIM = 4
OBSERVATION_FEATURE_DIM = (
    _OBS_NUMERIC_DIM
    + len(_PHASES)
    + _CARD_SUMMARY_DIM
    + _CARD_SUMMARY_DIM
    + len(_SET_COLORS) * 2
    + _OPPONENT_SUMMARY_DIM
)

_ACTION_NUMERIC_DIM = 9
ACTION_FEATURE_DIM = (
    len(_ACTION_TYPES)
    + _ACTION_NUMERIC_DIM
    + _CARD_SUMMARY_DIM
    + len(_COLORS)
)


@dataclass(frozen=True, slots=True)
class EncodedActionBatch:
    schema_version: str
    observation_features: tuple[float, ...]
    action_features: tuple[tuple[float, ...], ...]
    actions: tuple[Action, ...]


def encode_observation(observation: Observation) -> tuple[float, ...]:
    own_property_count = sum(len(cards) for cards in observation.properties.values())
    own_completed_sets = _completed_set_count(observation.properties)
    opponent_hand_total = sum(o.hand_size for o in observation.opponents.values())
    opponent_bank_total = sum(o.bank_value for o in observation.opponents.values())
    opponent_completed = sum(o.completed_sets for o in observation.opponents.values())
    opponent_property_total = sum(
        len(cards)
        for opponent in observation.opponents.values()
        for cards in opponent.properties.values()
    )
    pending = observation.pending
    numeric = (
        _scale(observation.turn, 100.0),
        _scale(len(observation.hand), 20.0),
        _scale(len(observation.bank), 20.0),
        _scale(sum(card.value for card in observation.bank), 50.0),
        _scale(own_property_count, 30.0),
        _scale(own_completed_sets, 3.0),
        _scale(observation.actions_taken, 3.0),
        _scale(observation.actions_left, 3.0),
        _scale(observation.discard_required, 10.0),
        _scale(len(observation.opponents), 4.0),
        _scale(opponent_hand_total, 40.0),
        _scale(opponent_bank_total, 100.0),
        _scale(opponent_completed, 12.0),
        _scale(opponent_property_total, 100.0),
        _scale(pending.amount if pending is not None else 0, 10.0),
        1.0 if pending is not None and pending.negated else 0.0,
    )
    features = (
        numeric
        + _one_hot(observation.phase, _PHASES)
        + _card_summary(observation.hand)
        + _card_summary(observation.bank)
        + _property_color_features(observation.properties)
        + (0.0,) * _OPPONENT_SUMMARY_DIM
    )
    opponent_features = (
        _scale(opponent_hand_total, 40.0),
        _scale(opponent_bank_total, 100.0),
        _scale(opponent_completed, 12.0),
        _scale(opponent_property_total, 100.0),
    )
    return features[:-_OPPONENT_SUMMARY_DIM] + opponent_features


def encode_action(observation: Observation, action: Action) -> tuple[float, ...]:
    related_cards = _related_cards(observation, action)
    action_color = _action_color(action)
    numeric = (
        _scale(len(related_cards), 10.0),
        _scale(sum(card.value for card in related_cards), 30.0),
        _scale(_payment_card_count(action), 10.0),
        _scale(_target_player_index(observation, action), 5.0),
        1.0 if isinstance(action, RespondJustSayNo) and action.accept else 0.0,
        1.0 if isinstance(action, RespondJustSayNo) and not action.accept else 0.0,
        1.0 if _has_target_player(action) else 0.0,
        1.0 if action_color is not None else 0.0,
        1.0 if isinstance(action, EndTurn) else 0.0,
    )
    features = (
        _action_type_one_hot(action)
        + numeric
        + _card_summary(related_cards)
        + _one_hot(action_color, _COLORS)
    )
    if len(features) != ACTION_FEATURE_DIM:
        raise AssertionError("action feature dimension mismatch")
    return features


def encode_legal_actions(
    observation: Observation, legal_actions: list[Action]
) -> EncodedActionBatch:
    return EncodedActionBatch(
        schema_version=FEATURE_SCHEMA_VERSION,
        observation_features=encode_observation(observation),
        action_features=tuple(encode_action(observation, action) for action in legal_actions),
        actions=tuple(legal_actions),
    )


def _scale(value: int | float, denominator: float) -> float:
    return float(value) / denominator


def _one_hot(value: _T | None, choices: tuple[_T, ...]) -> tuple[float, ...]:
    return tuple(1.0 if value == choice else 0.0 for choice in choices)


def _card_summary(cards: list[Card] | tuple[Card, ...]) -> tuple[float, ...]:
    kind_counts = tuple(
        _scale(sum(card.kind == kind for card in cards), 10.0) for kind in _CARD_KINDS
    )
    subtype_counts = tuple(
        _scale(sum(card.action_subtype == subtype for card in cards), 10.0)
        for subtype in _ACTION_SUBTYPES
    )
    color_counts = tuple(
        _scale(sum(color in _card_colors(card) for card in cards), 10.0) for color in _COLORS
    )
    value_features = (_scale(sum(card.value for card in cards), 50.0), _scale(len(cards), 20.0))
    return kind_counts + subtype_counts + color_counts + value_features


def _property_color_features(
    properties: dict[PropertyColor, list[Card]] | dict[PropertyColor, tuple[Card, ...]]
) -> tuple[float, ...]:
    counts = tuple(_scale(len(properties.get(color, ())), 5.0) for color in _SET_COLORS)
    completed = tuple(
        1.0 if len(properties.get(color, ())) >= SET_SIZE_BY_COLOR[color] else 0.0
        for color in _SET_COLORS
    )
    return counts + completed


def _completed_set_count(
    properties: dict[PropertyColor, list[Card]] | dict[PropertyColor, tuple[Card, ...]]
) -> int:
    return sum(
        len(properties.get(color, ())) >= SET_SIZE_BY_COLOR[color] for color in _SET_COLORS
    )


def _card_colors(card: Card) -> tuple[PropertyColor, ...]:
    if card.color is not None:
        return (card.color,)
    return card.colors


def _action_type_one_hot(action: Action) -> tuple[float, ...]:
    return tuple(1.0 if isinstance(action, action_type) else 0.0 for action_type in _ACTION_TYPES)


def _related_cards(observation: Observation, action: Action) -> tuple[Card, ...]:
    card_ids = _action_card_ids(action)
    cards = tuple(_visible_card_by_id(observation, card_id) for card_id in card_ids)
    return tuple(card for card in cards if card is not None)


def _action_card_ids(action: Action) -> tuple[str, ...]:
    if isinstance(action, (BankCard, PlayProperty, DiscardCard, RearrangeProperty)):
        return (action.card_id,)
    if isinstance(action, PlayRent):
        ids = [action.card_id]
        if action.double_rent_card_id is not None:
            ids.append(action.double_rent_card_id)
        return tuple(ids)
    if isinstance(action, PlayActionCard):
        return tuple(
            card_id
            for card_id in (
                action.card_id,
                action.target_card_id,
                action.offered_card_id,
                action.requested_card_id,
            )
            if card_id is not None
        )
    if isinstance(action, PayWithAssets):
        return action.card_ids
    if isinstance(action, RespondJustSayNo):
        return () if action.card_id is None else (action.card_id,)
    return ()


def _visible_card_by_id(observation: Observation, card_id: str) -> Card | None:
    for card in observation.hand:
        if card.id == card_id:
            return card
    for card in observation.bank:
        if card.id == card_id:
            return card
    for cards in observation.properties.values():
        for card in cards:
            if card.id == card_id:
                return card
    for opponent in observation.opponents.values():
        for cards in opponent.properties.values():
            for card in cards:
                if card.id == card_id:
                    return card
    return None


def _action_color(action: Action) -> PropertyColor | None:
    if isinstance(action, (PlayProperty, RearrangeProperty)):
        return action.color
    if isinstance(action, (PlayRent, PlayActionCard)):
        return action.color
    return None


def _payment_card_count(action: Action) -> int:
    if isinstance(action, PayWithAssets):
        return len(action.card_ids)
    return 0


def _has_target_player(action: Action) -> bool:
    return _target_player_id(action) is not None


def _target_player_id(action: Action) -> str | None:
    if isinstance(action, (PlayRent, PlayActionCard)):
        return action.target_player_id
    return None


def _target_player_index(observation: Observation, action: Action) -> int:
    target = _target_player_id(action)
    if target is None:
        return 0
    player_ids = (observation.player_id,) + tuple(sorted(observation.opponents))
    try:
        return player_ids.index(target)
    except ValueError:
        return 0

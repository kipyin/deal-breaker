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
    RENT_LADDER_BY_COLOR,
    SET_SIZE_BY_COLOR,
    ActionSubtype,
    Card,
    CardKind,
    PropertyColor,
)
from dbreaker.engine.fair_visibility import (
    hand_attack_steal_counts,
    natural_property_visible_by_color,
    unseen_action_subtype_count,
    unseen_natural_property_by_color,
    visible_action_subtype_count,
    wild_property_visible_count,
    wild_unseen_count,
)
from dbreaker.engine.observation import Observation, OpponentObservation
from dbreaker.engine.rules import GamePhase

FEATURE_SCHEMA_VERSION = "dbreaker-ml-features-v3"

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
_PENDING_KINDS = ("payment", "sly_deal", "forced_deal", "deal_breaker")
_ACTION_EXTRA_DIM = 16
_T = TypeVar("_T")

_OBS_NUMERIC_DIM = 16
_CARD_SUMMARY_DIM = len(_CARD_KINDS) + len(_ACTION_SUBTYPES) + len(_COLORS) + 2
_OPPONENT_SUMMARY_DIM = 4

# v1-style base block
_OBS_BASE_DIM = (
    _OBS_NUMERIC_DIM
    + len(_PHASES)
    + _CARD_SUMMARY_DIM
    + _CARD_SUMMARY_DIM
    + len(_SET_COLORS) * 2
    + _OPPONENT_SUMMARY_DIM
)

_PER_COLOR_OWN_DIM = 4
_PER_COLOR_OPP_DIM = 3
_OPPONENT_SLOT_COUNT = 4
_OPPONENT_SLOT_DIM = 5
# kind one-hot (4) + role (3) + amount/20 + negated + high-stakes
_PENDING_EXTRA_DIM = len(_PENDING_KINDS) + 3 + 3
_HAND_HEURISTIC_DIM = 8
# Per-color unseen/visible natural property, wild vis/unseen, steal cards in hand,
# unseen/visible counts for high-impact action subtypes (fair deck arithmetic).
_FAIR_INFORMATION_DIM = len(_SET_COLORS) * 2 + 2 + 3 + 4

OBSERVATION_EXTRA_DIM = (
    len(_SET_COLORS) * _PER_COLOR_OWN_DIM
    + len(_SET_COLORS) * _PER_COLOR_OPP_DIM
    + _OPPONENT_SLOT_COUNT * _OPPONENT_SLOT_DIM
    + _PENDING_EXTRA_DIM
    + _HAND_HEURISTIC_DIM
    + _FAIR_INFORMATION_DIM
)
OBSERVATION_FEATURE_DIM = _OBS_BASE_DIM + OBSERVATION_EXTRA_DIM

_ACTION_NUMERIC_DIM = 9
_ACTION_V1_DIM = (
    len(_ACTION_TYPES)
    + _ACTION_NUMERIC_DIM
    + _CARD_SUMMARY_DIM
    + len(_COLORS)
)
ACTION_FEATURE_DIM = _ACTION_V1_DIM + _ACTION_EXTRA_DIM


@dataclass(frozen=True, slots=True)
class EncodedActionBatch:
    schema_version: str
    observation_features: tuple[float, ...]
    action_features: tuple[tuple[float, ...], ...]
    actions: tuple[Action, ...]


@dataclass(frozen=True, slots=True)
class _EncodingContext:
    card_by_id: dict[str, Card]
    zone_by_id: dict[str, str]
    value_by_id: dict[str, int]


def encode_observation(observation: Observation) -> tuple[float, ...]:
    base = _encode_observation_base(observation)
    assert len(base) == _OBS_BASE_DIM, f"{len(base)} != {_OBS_BASE_DIM}"
    extra = (
        _encode_per_color_own(observation)
        + _encode_per_color_opponent_aggregate(observation)
        + _encode_opponent_slots(observation)
        + _encode_pending_context(observation)
        + _encode_hand_heuristics(observation)
        + _encode_fair_information(observation)
    )
    assert len(extra) == OBSERVATION_EXTRA_DIM, f"{len(extra)} != {OBSERVATION_EXTRA_DIM}"
    return base + extra


def encode_action(
    observation: Observation, action: Action, *, context: _EncodingContext | None = None
) -> tuple[float, ...]:
    ctx = context or _build_encoding_context(observation)
    related_cards = _related_cards(observation, action, context=ctx)
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
    v1 = (
        _action_type_one_hot(action)
        + numeric
        + _card_summary(related_cards)
        + _one_hot(action_color, _COLORS)
    )
    assert len(v1) == _ACTION_V1_DIM
    extra = _encode_action_impact(observation, action, context=ctx)
    assert len(extra) == _ACTION_EXTRA_DIM
    return v1 + extra


def encode_legal_actions(
    observation: Observation, legal_actions: list[Action]
) -> EncodedActionBatch:
    context = _build_encoding_context(observation)
    return EncodedActionBatch(
        schema_version=FEATURE_SCHEMA_VERSION,
        observation_features=encode_observation(observation),
        action_features=tuple(
            encode_action(observation, action, context=context) for action in legal_actions
        ),
        actions=tuple(legal_actions),
    )


def _encode_observation_base(observation: Observation) -> tuple[float, ...]:
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


def _encode_per_color_own(observation: Observation) -> tuple[float, ...]:
    out: list[float] = []
    for color in _SET_COLORS:
        need = SET_SIZE_BY_COLOR[color]
        cnt = len(observation.properties.get(color, ()))
        completed = 1.0 if cnt >= need else 0.0
        missing = _scale(max(0, need - cnt), 5.0)
        progress = min(1.0, float(cnt) / float(need)) if need else 0.0
        rent = _scale(_rent_from_property_count(color, cnt), 20.0)
        out.extend((completed, missing, progress, rent))
    return tuple(out)


def _encode_per_color_opponent_aggregate(observation: Observation) -> tuple[float, ...]:
    opps = list(observation.opponents.values())
    out: list[float] = []
    for color in _SET_COLORS:
        need = SET_SIZE_BY_COLOR[color]
        counts = [len(opp.properties.get(color, ())) for opp in opps] if opps else [0]
        max_cnt = max(counts) if counts else 0
        max_prog = min(1.0, float(max_cnt) / float(need)) if need else 0.0
        one_away = sum(1 for c in counts if need > 1 and c == need - 1)
        one_away_scaled = _scale(one_away, 3.0)
        any_complete = 1.0 if any(c >= need for c in counts) and need else 0.0
        out.extend((max_prog, one_away_scaled, any_complete))
    return tuple(out)


def _encode_opponent_slots(observation: Observation) -> tuple[float, ...]:
    opps = _opponents_sorted_by_threat(observation)
    slots: list[tuple[float, ...]] = []
    for i in range(_OPPONENT_SLOT_COUNT):
        if i < len(opps):
            o = opps[i]
            tot_props = sum(len(cards) for cards in o.properties.values())
            max_pressure = 0.0
            for c in _SET_COLORS:
                need = SET_SIZE_BY_COLOR[c]
                n = len(o.properties.get(c, ()))
                max_pressure = max(max_pressure, min(1.0, float(n) / float(need)))
            slots.append(
                (
                    _scale(o.hand_size, 20.0),
                    _scale(o.bank_value, 100.0),
                    _scale(o.completed_sets, 5.0),
                    _scale(tot_props, 30.0),
                    max_pressure,
                )
            )
        else:
            slots.append((0.0, 0.0, 0.0, 0.0, 0.0))
    flat: list[float] = []
    for t in slots:
        flat.extend(t)
    return tuple(flat)


def _opponents_sorted_by_threat(observation: Observation) -> list[OpponentObservation]:
    opps: list[OpponentObservation] = list(observation.opponents.values())

    def sort_key(o: OpponentObservation) -> tuple[int, int, int, int]:
        tot = sum(len(cards) for cards in o.properties.values())
        return (-o.completed_sets, -tot, -o.bank_value, -o.hand_size)

    return sorted(opps, key=sort_key)


def _encode_pending_context(observation: Observation) -> tuple[float, ...]:
    p = observation.pending
    if p is None:
        return (0.0,) * _PENDING_EXTRA_DIM
    kind_oh = _one_hot_str(p.kind, _PENDING_KINDS)
    is_actor = 1.0 if p.actor_id == observation.player_id else 0.0
    is_target = 1.0 if p.target_id == observation.player_id else 0.0
    is_respond = 1.0 if p.respond_player_id == observation.player_id else 0.0
    amount = _scale(p.amount, 20.0)
    neg = 1.0 if p.negated else 0.0
    high = 1.0 if p.amount >= 5 or p.kind == "deal_breaker" else 0.0
    return kind_oh + (is_actor, is_target, is_respond, amount, neg, high)


def _one_hot_str(value: str, choices: tuple[str, ...]) -> tuple[float, ...]:
    return tuple(1.0 if value == choice else 0.0 for choice in choices)


def _encode_hand_heuristics(observation: Observation) -> tuple[float, ...]:
    h = observation.hand
    st = ActionSubtype
    return (
        _scale(sum(1 for c in h if c.action_subtype == st.JUST_SAY_NO), 3.0),
        _scale(sum(1 for c in h if c.action_subtype == st.DOUBLE_THE_RENT), 2.0),
        _scale(sum(1 for c in h if c.action_subtype == st.PASS_GO), 10.0),
        _scale(sum(1 for c in h if c.action_subtype == st.SLY_DEAL), 3.0),
        _scale(sum(1 for c in h if c.action_subtype == st.FORCED_DEAL), 3.0),
        _scale(sum(1 for c in h if c.action_subtype == st.DEAL_BREAKER), 2.0),
        _scale(sum(1 for c in h if c.action_subtype == st.DEBT_COLLECTOR), 3.0),
        _scale(
            sum(
                1
                for c in h
                if c.action_subtype in (ActionSubtype.HOUSE, ActionSubtype.HOTEL)
            ),
            3.0,
        ),
    )


def _encode_fair_information(observation: Observation) -> tuple[float, ...]:
    unseen = unseen_natural_property_by_color(observation)
    visible_nat = natural_property_visible_by_color(observation)
    wild_vis = wild_property_visible_count(observation)
    wild_remain = wild_unseen_count(observation)
    db, sly, forced = hand_attack_steal_counts(observation)
    parts: list[float] = []
    for color in _SET_COLORS:
        parts.append(_scale(unseen[color], 5.0))
    for color in _SET_COLORS:
        parts.append(_scale(visible_nat[color], 5.0))
    parts.extend(
        (
            _scale(wild_vis, 10.0),
            _scale(wild_remain, 10.0),
            _scale(db, 3.0),
            _scale(sly, 3.0),
            _scale(forced, 3.0),
        )
    )
    st = ActionSubtype
    parts.extend(
        (
            _scale(unseen_action_subtype_count(observation, st.DEAL_BREAKER), 2.0),
            _scale(unseen_action_subtype_count(observation, st.JUST_SAY_NO), 3.0),
            _scale(visible_action_subtype_count(observation, st.DEAL_BREAKER), 2.0),
            _scale(visible_action_subtype_count(observation, st.JUST_SAY_NO), 3.0),
        )
    )
    out = tuple(parts)
    assert len(out) == _FAIR_INFORMATION_DIM, f"{len(out)} != {_FAIR_INFORMATION_DIM}"
    return out


def _encode_action_impact(
    observation: Observation, action: Action, *, context: _EncodingContext | None = None
) -> tuple[float, ...]:
    ctx = context or _build_encoding_context(observation)
    play_complete = 0.0
    progress_delta = 0.0
    if isinstance(action, PlayProperty):
        color = action.color
        need = SET_SIZE_BY_COLOR[color]
        cur = len(observation.properties.get(color, ()))
        if cur + 1 >= need:
            play_complete = 1.0
        progress_delta = _scale(1, float(need))
    rent_mag = 0.0
    double_rent = 0.0
    if isinstance(action, PlayRent) and action.color is not None:
        color = action.color
        nprops = len(observation.properties.get(color, ()))
        rent_mag = _scale(_rent_from_property_count(color, nprops), 20.0)
        double_rent = 1.0 if action.double_rent_card_id is not None else 0.0
    target_strength = 0.0
    tid = _target_player_id(action)
    if tid is not None and tid in observation.opponents:
        o = observation.opponents[tid]
        tot = sum(len(cards) for cards in o.properties.values())
        target_strength = _scale(o.completed_sets, 5.0) + _scale(tot, 30.0)
    pay_sum = 0.0
    pay_ratio = 0.0
    pay_prop = 0.0
    pay_n = 0.0
    if isinstance(action, PayWithAssets):
        pay_sum = _scale(
            sum(_asset_value_for_payment(observation, cid, context=ctx) for cid in action.card_ids),
            50.0,
        )
        pend = observation.pending
        if pend is not None and pend.amount > 0:
            tot = float(
                sum(
                    _asset_value_for_payment(observation, cid, context=ctx)
                    for cid in action.card_ids
                )
            )
            pay_ratio = _scale(tot, float(pend.amount))
        pay_prop = (
            1.0
            if any(
                _card_in_zone(observation, cid, context=ctx) == "property"
                for cid in action.card_ids
            )
            else 0.0
        )
        pay_n = _scale(len(action.card_ids), 10.0)
    is_attack = 0.0
    is_building = 0.0
    if isinstance(action, PlayActionCard):
        card = _visible_card_by_id(observation, action.card_id, context=ctx)
        if card is not None and card.action_subtype is not None:
            st = card.action_subtype
            steal_types = (
                ActionSubtype.DEAL_BREAKER,
                ActionSubtype.SLY_DEAL,
                ActionSubtype.FORCED_DEAL,
            )
            if st in steal_types:
                is_attack = 1.0
            if st in (ActionSubtype.HOUSE, ActionSubtype.HOTEL):
                is_building = 1.0
    jsn_block = 0.0
    if isinstance(action, RespondJustSayNo) and not action.accept:
        pend = observation.pending
        if pend is not None and (pend.amount >= 5 or pend.kind == "deal_breaker"):
            jsn_block = 1.0
    bank_v = 0.0
    if isinstance(action, BankCard):
        c = _visible_card_by_id(observation, action.card_id, context=ctx)
        if c is not None:
            bank_v = _scale(c.value, 10.0)
    return (
        play_complete,
        progress_delta,
        rent_mag,
        double_rent,
        target_strength,
        pay_sum,
        pay_ratio,
        pay_prop,
        pay_n,
        is_attack,
        is_building,
        jsn_block,
        bank_v,
        0.0,
        0.0,
        0.0,
    )


def _card_in_zone(
    observation: Observation, card_id: str, *, context: _EncodingContext | None = None
) -> str:
    if context is not None:
        return context.zone_by_id.get(card_id, "unknown")
    for card in observation.hand:
        if card.id == card_id:
            return "hand"
    for card in observation.bank:
        if card.id == card_id:
            return "bank"
    for cards in observation.properties.values():
        for card in cards:
            if card.id == card_id:
                return "property"
    for opp in observation.opponents.values():
        for cards in opp.properties.values():
            for card in cards:
                if card.id == card_id:
                    return "property"
    return "unknown"


def _asset_value_for_payment(
    observation: Observation, card_id: str, *, context: _EncodingContext | None = None
) -> int:
    if context is not None:
        return context.value_by_id.get(card_id, 0)
    for card in observation.hand:
        if card.id == card_id:
            return card.value
    for card in observation.bank:
        if card.id == card_id:
            return card.value
    for cards in observation.properties.values():
        for card in cards:
            if card.id == card_id:
                return card.value
    for opp in observation.opponents.values():
        for cards in opp.properties.values():
            for card in cards:
                if card.id == card_id:
                    return card.value
    return 0


def _rent_from_property_count(color: PropertyColor, n_props: int) -> int:
    ladder = RENT_LADDER_BY_COLOR.get(color)
    if not ladder or n_props <= 0:
        return 0
    return ladder[min(n_props, len(ladder)) - 1]


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


def _related_cards(
    observation: Observation, action: Action, *, context: _EncodingContext | None = None
) -> tuple[Card, ...]:
    ctx = context or _build_encoding_context(observation)
    card_ids = _action_card_ids(action)
    cards = tuple(
        _visible_card_by_id(observation, card_id, context=ctx) for card_id in card_ids
    )
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


def _visible_card_by_id(
    observation: Observation, card_id: str, *, context: _EncodingContext | None = None
) -> Card | None:
    if context is not None:
        return context.card_by_id.get(card_id)
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


def _build_encoding_context(observation: Observation) -> _EncodingContext:
    card_by_id: dict[str, Card] = {}
    zone_by_id: dict[str, str] = {}
    value_by_id: dict[str, int] = {}

    def add(card: Card, zone: str) -> None:
        if card.id in card_by_id:
            return
        card_by_id[card.id] = card
        zone_by_id[card.id] = zone
        value_by_id[card.id] = card.value

    for card in observation.hand:
        add(card, "hand")
    for card in observation.bank:
        add(card, "bank")
    for cards in observation.properties.values():
        for card in cards:
            add(card, "property")
    for opponent in observation.opponents.values():
        for cards in opponent.properties.values():
            for card in cards:
                add(card, "property")

    return _EncodingContext(
        card_by_id=card_by_id,
        zone_by_id=zone_by_id,
        value_by_id=value_by_id,
    )


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

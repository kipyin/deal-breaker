from __future__ import annotations

import json

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
    action_to_payload,
)
from dbreaker.engine.cards import (
    BUILDABLE_COLORS,
    RENT_LADDER_BY_COLOR,
    SET_SIZE_BY_COLOR,
    ActionSubtype,
    Card,
    CardKind,
    PropertyColor,
)
from dbreaker.engine.fair_visibility import unseen_natural_property_by_color
from dbreaker.engine.observation import Observation
from dbreaker.strategies.base import StrategyDecision
from dbreaker.strategies.heuristic import (
    BasicHeuristicStrategy,
    _choose_discard_action,
    _choose_pending_action,
    _payment_total,
)
from dbreaker.strategies.heuristic import (
    _card_value as card_value_in_cards,
)


class HumanLikeStrategy(BasicHeuristicStrategy):
    """Heuristic policy using only fair observation plus public deck counts."""

    name = "human_like"

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
                reason_summary=f"{self.name} discarded a low-value card.",
            )
        ranked = max(
            legal_actions,
            key=lambda a: (
                _primary_utility(observation, a) + _lookahead_bonus(observation, a),
                _action_sort_key(a),
            ),
        )
        return StrategyDecision(
            action=ranked,
            reason_summary=f"{self.name} picked highest-scoring legal action.",
        )


def _action_sort_key(action: Action) -> str:
    return json.dumps(action_to_payload(action), sort_keys=True)


def _primary_utility(observation: Observation, action: Action) -> float:
    match action:
        case DrawCards():
            return 20.0
        case BankCard():
            return _score_bank(observation, action)
        case PlayProperty():
            return _score_play_property(observation, action)
        case PlayRent():
            return _score_play_rent(observation, action)
        case PlayActionCard():
            return _score_play_action_card(observation, action)
        case PayWithAssets():
            return -float(_payment_total(observation, action))
        case DiscardCard():
            return -float(max(0, card_value_in_cards(observation.hand, action.card_id)))
        case RearrangeProperty():
            return _score_rearrange(observation, action)
        case EndTurn():
            return 0.25
        case RespondJustSayNo():
            return _score_respond_just_say_no(observation, action)
        case _:
            return 0.0


def _lookahead_bonus(observation: Observation, action: Action) -> float:
    left = observation.actions_left
    if left <= 1:
        return 0.0
    match action:
        case PlayProperty() | PlayRent() | PlayActionCard():
            return 0.35 * float(left - 1)
        case BankCard():
            return 0.12 * float(left - 1)
        case DrawCards():
            return 0.5
        case RearrangeProperty():
            return 0.05
        case _:
            return 0.0


def _rent_from_property_count(color: PropertyColor, n_props: int) -> int:
    ladder = RENT_LADDER_BY_COLOR.get(color)
    if not ladder or n_props <= 0:
        return 0
    return ladder[min(n_props, len(ladder)) - 1]


def _visible_card(observation: Observation, card_id: str) -> Card | None:
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
    for opp in observation.opponents.values():
        for card in opp.bank:
            if card.id == card_id:
                return card
        for cards in opp.properties.values():
            for card in cards:
                if card.id == card_id:
                    return card
    return None


def _score_bank(observation: Observation, action: BankCard) -> float:
    card = _visible_card(observation, action.card_id)
    if card is None:
        return -50.0
    hand_n = len(observation.hand)
    match card.kind:
        case CardKind.MONEY:
            value = float(card.value)
            if hand_n >= 6:
                return 2.0 + value * 0.05
            return 4.0 - value * 0.15
        case CardKind.PROPERTY | CardKind.WILD_PROPERTY:
            return -18.0 + float(card.value) * 0.12
        case CardKind.RENT | CardKind.ACTION:
            return 0.8


def _completion_key_risk(
    observation: Observation,
    color: PropertyColor,
    *,
    completes: bool,
) -> float:
    if not completes:
        return 0.0
    unseen = unseen_natural_property_by_color(observation)
    pressure = 0.0
    for opp in observation.opponents.values():
        pressure += float(opp.completed_sets)
        for c, need in SET_SIZE_BY_COLOR.items():
            n = len(opp.properties.get(c, ()))
            if need > 1 and n == need - 1:
                pressure += 0.45
    raw_unseen = float(unseen.get(color, 0))
    return min(8.5, raw_unseen * 0.28 * (1.0 + pressure * 0.14))


def _score_play_property(observation: Observation, action: PlayProperty) -> float:
    color = action.color
    need = SET_SIZE_BY_COLOR[color]
    cur = len(observation.properties.get(color, ()))
    completes = cur + 1 >= need
    progress = float(cur + 1) / float(need)
    rent_bonus = _rent_from_property_count(color, cur + 1) * 0.16
    score = progress * 9.0 + rent_bonus
    if completes:
        score += 25.0
    score -= _completion_key_risk(observation, color, completes=completes)
    return score


def _score_play_rent(observation: Observation, action: PlayRent) -> float:
    color = action.color
    if color is None:
        return 0.0
    n = len(observation.properties.get(color, ()))
    rent = _rent_from_property_count(color, n)
    if action.double_rent_card_id is not None:
        rent *= 2
    target_rich = 0.0
    target = observation.opponents.get(action.target_player_id)
    if target is not None:
        target_rich = (
            target.bank_value * 0.052
            + float(target.completed_sets) * 3.1
            + float(sum(len(cards) for cards in target.properties.values())) * 0.085
        )
    return rent * 0.62 + target_rich


def _property_synergy_score(observation: Observation, card: Card) -> float:
    if card.kind not in (CardKind.PROPERTY, CardKind.WILD_PROPERTY):
        return float(card.value) * 0.22
    score = float(card.value) * 0.14
    for color in card.playable_colors:
        if color == PropertyColor.ANY:
            continue
        need = SET_SIZE_BY_COLOR[color]
        have = len(observation.properties.get(color, ()))
        missing_upper = max(0, need - have)
        if missing_upper == 0:
            score += 6.0
        elif missing_upper == 1:
            score += 11.5
        elif missing_upper == 2:
            score += 4.0
    return score


def _score_play_action_card(observation: Observation, action: PlayActionCard) -> float:
    card = _visible_card(observation, action.card_id)
    if card is None or card.action_subtype is None:
        return -1.0
    match card.action_subtype:
        case ActionSubtype.PASS_GO:
            return 11.0 + max(0, 7 - len(observation.hand)) * 0.22
        case ActionSubtype.ITS_MY_BIRTHDAY:
            return 7.0
        case ActionSubtype.DEBT_COLLECTOR:
            return _score_debt_collector(observation, action)
        case ActionSubtype.HOUSE:
            return _score_build(observation, action, is_hotel=False)
        case ActionSubtype.HOTEL:
            return _score_build(observation, action, is_hotel=True)
        case ActionSubtype.SLY_DEAL:
            return _score_sly_deal(observation, action)
        case ActionSubtype.FORCED_DEAL:
            return _score_forced_deal(observation, action)
        case ActionSubtype.DEAL_BREAKER:
            return _score_deal_breaker(observation, action)
        case ActionSubtype.JUST_SAY_NO | ActionSubtype.DOUBLE_THE_RENT:
            return 0.25


def _score_debt_collector(observation: Observation, action: PlayActionCard) -> float:
    tid = action.target_player_id
    if tid is None or tid not in observation.opponents:
        return 1.2
    opponent = observation.opponents[tid]
    return 4.2 + opponent.bank_value * 0.078 + float(opponent.completed_sets) * 2.05


def _score_build(observation: Observation, action: PlayActionCard, *, is_hotel: bool) -> float:
    color = action.color
    if color is None or color not in BUILDABLE_COLORS:
        return 0.0
    n = len(observation.properties.get(color, []))
    rent = _rent_from_property_count(color, n)
    mult = 1.35 if is_hotel else 1.0
    return 8.0 + rent * 0.38 * mult


def _score_sly_deal(observation: Observation, action: PlayActionCard) -> float:
    if action.target_card_id is None:
        return 1.0
    target = _visible_card(observation, action.target_card_id)
    if target is None:
        return 0.0
    score = float(target.value) * 0.42 + _property_synergy_score(observation, target) * 0.55
    return score


def _score_forced_deal(observation: Observation, action: PlayActionCard) -> float:
    if action.offered_card_id is None or action.requested_card_id is None:
        return 0.0
    offered = _visible_card(observation, action.offered_card_id)
    wanted = _visible_card(observation, action.requested_card_id)
    if offered is None or wanted is None:
        return 0.0
    gain = _property_synergy_score(observation, wanted)
    loss = _property_synergy_score(observation, offered)
    return 5.5 + gain - loss * 0.92


def _score_deal_breaker(observation: Observation, action: PlayActionCard) -> float:
    if action.target_player_id is None or action.color is None:
        return 1.0
    opponent = observation.opponents.get(action.target_player_id)
    if opponent is None:
        return 0.0
    stolen = opponent.properties.get(action.color, ())
    return 19.0 + sum(c.value for c in stolen) * 0.48 + float(len(stolen)) * 3.0


def _current_color_for_card(observation: Observation, card_id: str) -> PropertyColor | None:
    for color, cards in observation.properties.items():
        for card in cards:
            if card.id == card_id:
                return color
    return None


def _score_rearrange(observation: Observation, action: RearrangeProperty) -> float:
    old = _current_color_for_card(observation, action.card_id)
    new = action.color
    if old is None or old == new:
        return 0.0
    old_need = SET_SIZE_BY_COLOR[old]
    new_need = SET_SIZE_BY_COLOR[new]
    old_cnt = len(observation.properties.get(old, ()))
    new_cnt = len(observation.properties.get(new, ()))
    old_prog_before = float(old_cnt) / float(old_need)
    new_prog_before = float(new_cnt) / float(new_need)
    old_prog_after = float(old_cnt - 1) / float(old_need)
    new_prog_after = float(new_cnt + 1) / float(new_need)
    delta = (new_prog_after - new_prog_before) + 0.45 * (old_prog_after - old_prog_before)
    return 1.2 + 5.5 * delta


def _score_respond_just_say_no(observation: Observation, action: RespondJustSayNo) -> float:
    pending = observation.pending
    high = pending is not None and (pending.amount >= 5 or pending.kind == "deal_breaker")
    if high:
        return 60.0 if not action.accept else 0.5
    if action.accept:
        return 10.5
    return -4.5

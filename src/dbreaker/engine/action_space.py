from __future__ import annotations

from itertools import product

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
from dbreaker.engine.cards import ActionSubtype, CardKind, PropertyColor
from dbreaker.engine.payment import legal_payment_selections
from dbreaker.engine.rules import GamePhase
from dbreaker.engine.state import GameState


def legal_actions(state: GameState, player_id: str) -> list[Action]:
    if state.winner_id is not None:
        return []

    if state.phase == GamePhase.PAYMENT:
        pending = state.pending_payment
        if pending is None or pending.payer_id != player_id:
            return []
        return [
            PayWithAssets(card_ids=tuple(card.id for card in selection.cards))
            for selection in legal_payment_selections(state.players[player_id], pending.amount)
        ]

    if state.phase == GamePhase.RESPOND:
        pending_effect = state.pending_effect
        if pending_effect is None or pending_effect.respond_player_id != player_id:
            return []
        player = state.players[player_id]
        response_actions: list[Action] = [RespondJustSayNo(card_id=None, accept=True)]
        response_actions.extend(
            RespondJustSayNo(card_id=card.id, accept=False)
            for card in player.hand
            if card.action_subtype == ActionSubtype.JUST_SAY_NO
        )
        return response_actions

    if player_id != state.current_player_id:
        return []
    if state.phase == GamePhase.DRAW:
        return [DrawCards()]

    player = state.players[player_id]
    if state.phase == GamePhase.DISCARD:
        if len(player.hand) <= state.rules.hand_limit:
            return [EndTurn()]
        return [DiscardCard(card_id=card.id) for card in player.hand]

    actions: list[Action] = []
    actions_left = state.rules.actions_per_turn - state.actions_taken
    for card in player.hand:
        if actions_left > 0:
            actions.append(BankCard(card_id=card.id))
        if card.kind in {CardKind.PROPERTY, CardKind.WILD_PROPERTY}:
            for color in card.playable_colors:
                if color != PropertyColor.ANY and actions_left > 0:
                    actions.append(PlayProperty(card_id=card.id, color=color))
        elif card.kind == CardKind.RENT:
            if actions_left > 0:
                actions.extend(_rent_actions(state, player_id, card.id, card.colors))
        elif card.kind == CardKind.ACTION and card.action_subtype is not None and actions_left > 0:
            actions.extend(_action_card_actions(state, player_id, card.id, card.action_subtype))
    for color, cards in player.properties.items():
        for card in cards:
            for playable_color in card.playable_colors:
                if playable_color != color:
                    actions.append(RearrangeProperty(card_id=card.id, color=playable_color))
    actions.append(EndTurn())
    return actions


def _rent_actions(
    state: GameState, player_id: str, card_id: str, colors: tuple[PropertyColor, ...]
) -> list[Action]:
    player = state.players[player_id]
    double_cards = [
        card.id for card in player.hand if card.action_subtype == ActionSubtype.DOUBLE_THE_RENT
    ]
    chargeable_colors = tuple(
        color
        for color, cards in state.players[player_id].properties.items()
        if cards
    )
    if PropertyColor.ANY not in colors:
        chargeable_colors = tuple(color for color in chargeable_colors if color in colors)
    actions: list[Action] = []
    for opponent_id, color in product(
        (opponent for opponent in state.player_order if opponent != player_id),
        chargeable_colors,
    ):
        actions.append(PlayRent(card_id=card_id, target_player_id=opponent_id, color=color))
        if state.actions_taken + 2 <= state.rules.actions_per_turn:
            actions.extend(
                PlayRent(
                    card_id=card_id,
                    target_player_id=opponent_id,
                    color=color,
                    double_rent_card_id=double_card_id,
                )
                for double_card_id in double_cards
            )
    return actions


def _action_card_actions(
    state: GameState, player_id: str, card_id: str, subtype: ActionSubtype
) -> list[Action]:
    player = state.players[player_id]
    if subtype in {ActionSubtype.PASS_GO}:
        return [PlayActionCard(card_id=card_id)]
    if subtype in {ActionSubtype.HOUSE, ActionSubtype.HOTEL}:
        return [
            PlayActionCard(card_id=card_id, color=color)
            for color in player.properties
            if player.can_build(color, subtype)
        ]
    if subtype == ActionSubtype.DEBT_COLLECTOR:
        return [
            PlayActionCard(card_id=card_id, target_player_id=opponent_id)
            for opponent_id in state.player_order
            if opponent_id != player_id
        ]
    if subtype == ActionSubtype.SLY_DEAL:
        actions: list[Action] = []
        for opponent_id in state.player_order:
            if opponent_id == player_id:
                continue
            opponent = state.players[opponent_id]
            actions.extend(
                PlayActionCard(
                    card_id=card_id, target_player_id=opponent_id, target_card_id=card.id
                )
                for card, _color in opponent.non_full_property_assets()
            )
        return actions
    if subtype == ActionSubtype.FORCED_DEAL:
        own_cards = player.non_full_property_assets()
        actions = []
        for opponent_id in state.player_order:
            if opponent_id == player_id:
                continue
            for (own_card, _own_color), (target_card, _target_color) in product(
                own_cards, state.players[opponent_id].non_full_property_assets()
            ):
                actions.append(
                    PlayActionCard(
                        card_id=card_id,
                        target_player_id=opponent_id,
                        offered_card_id=own_card.id,
                        requested_card_id=target_card.id,
                    )
                )
        return actions
    if subtype == ActionSubtype.DEAL_BREAKER:
        actions = []
        for opponent_id in state.player_order:
            if opponent_id == player_id:
                continue
            opponent = state.players[opponent_id]
            actions.extend(
                PlayActionCard(card_id=card_id, target_player_id=opponent_id, color=color)
                for color in opponent.properties
                if opponent.is_full_set(color)
            )
        return actions
    if subtype == ActionSubtype.ITS_MY_BIRTHDAY:
        if len(state.player_order) <= 1:
            return []
        return [PlayActionCard(card_id=card_id)]
    return []

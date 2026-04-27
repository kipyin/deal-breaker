from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

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
    ActionSubtype,
    Card,
    CardKind,
    PropertyColor,
)
from dbreaker.engine.events import GameEvent
from dbreaker.engine.payment import is_legal_payment_selection
from dbreaker.engine.player import PlayerState
from dbreaker.engine.rules import GamePhase
from dbreaker.engine.state import GameState, PendingEffect, PendingPayment


@dataclass(frozen=True, slots=True)
class StepResult:
    accepted: bool
    events: list[GameEvent]


def resolve_action(state: GameState, player_id: str, action: Action) -> StepResult:
    if state.winner_id is not None:
        return _reject(state, player_id, action, "game already ended")
    if not _is_actor_for_phase(state, player_id):
        return _reject(state, player_id, action, "not current player")

    if isinstance(action, DrawCards):
        return _resolve_draw(state, player_id)

    if isinstance(action, DiscardCard):
        return _resolve_discard(state, player_id, action)

    if isinstance(action, PayWithAssets):
        return _resolve_payment(state, player_id, action)

    if isinstance(action, RespondJustSayNo):
        return _resolve_response(state, player_id, action)

    if state.phase not in {GamePhase.ACTION, GamePhase.DISCARD}:
        return _reject(state, player_id, action, f"cannot act during {state.phase.value} phase")

    if isinstance(action, EndTurn):
        if (
            state.phase == GamePhase.DISCARD
            and len(state.players[player_id].hand) > state.rules.hand_limit
        ):
            return _reject(state, player_id, action, "must discard down to hand limit")
        if (
            state.phase == GamePhase.ACTION
            and len(state.players[player_id].hand) > state.rules.hand_limit
        ):
            state.phase = GamePhase.DISCARD
            return StepResult(
                accepted=True,
                events=[
                    GameEvent(
                        type="discard_required",
                        turn=state.turn,
                        player=player_id,
                        action="end_turn",
                        reason_summary="Player must discard down to the hand limit.",
                    )
                ],
            )
        event = GameEvent(
            type="turn_ended",
            turn=state.turn,
            player=player_id,
            action="end_turn",
            reason_summary="Player ended turn.",
        )
        state.advance_turn()
        return StepResult(accepted=True, events=[event])

    if isinstance(action, BankCard):
        if not _can_take_counted_action(state, 1):
            return _reject(state, player_id, action, "action limit reached")
        player, card = state.players[player_id].remove_from_hand(action.card_id)
        if card is None:
            return _reject(state, player_id, action, "card not in hand")
        state.players[player_id] = player.add_to_bank(card)
        state.actions_taken += 1
        state.phase = state.next_phase_after_action()
        return StepResult(
            accepted=True,
            events=[
                GameEvent(
                    type="card_banked",
                    turn=state.turn,
                    player=player_id,
                    action="bank",
                    card=card.name,
                    reason_summary=f"{player_id} banked {card.name}.",
                )
            ],
        )

    if isinstance(action, PlayProperty):
        if not _can_take_counted_action(state, 1):
            return _reject(state, player_id, action, "action limit reached")
        player, card = state.players[player_id].remove_from_hand(action.card_id)
        if card is None:
            return _reject(state, player_id, action, "card not in hand")
        if card.kind not in {CardKind.PROPERTY, CardKind.WILD_PROPERTY}:
            return _reject(state, player_id, action, "card is not a property")
        if action.color not in card.playable_colors:
            return _reject(state, player_id, action, "property cannot use that color")
        updated_player = player.add_property(card, action.color)
        state.players[player_id] = updated_player
        state.actions_taken += 1
        state.phase = state.next_phase_after_action()
        events = [
            GameEvent(
                type="property_played",
                turn=state.turn,
                player=player_id,
                action="play_property",
                card=card.name,
                reason_summary=f"{player_id} played {card.name} as {action.color.value}.",
            )
        ]
        if updated_player.completed_set_count() >= state.rules.sets_to_win:
            state.winner_id = player_id
            state.phase = GamePhase.GAME_OVER
            events.append(
                GameEvent(
                    type="game_won",
                    turn=state.turn,
                    player=player_id,
                    result="winner",
                    reason_summary=(
                        f"{player_id} completed {state.rules.sets_to_win} property sets."
                    ),
                )
            )
        return StepResult(accepted=True, events=events)

    if isinstance(action, RearrangeProperty):
        return _resolve_rearrange(state, player_id, action)

    if isinstance(action, PlayRent):
        return _resolve_rent(state, player_id, action)

    if isinstance(action, PlayActionCard):
        return _resolve_action_card(state, player_id, action)

    return _reject(state, player_id, action, "unsupported action")


def _is_actor_for_phase(state: GameState, player_id: str) -> bool:
    if state.phase == GamePhase.PAYMENT and state.pending_payment is not None:
        return player_id == state.pending_payment.payer_id
    if state.phase == GamePhase.RESPOND and state.pending_effect is not None:
        return player_id == state.pending_effect.respond_player_id
    return player_id == state.current_player_id


def _reshuffle_discard_into_deck(state: GameState) -> bool:
    if state.deck or not state.discard or not state.rules.reshuffle_discard_when_deck_empty:
        return False
    cards = list(state.discard)
    state.discard.clear()
    seed_material = f"{state.seed!s}|{state.turn}|" + ",".join(c.id for c in cards)
    digest = hashlib.sha256(seed_material.encode()).hexdigest()[:16]
    random.Random(int(digest, 16)).shuffle(cards)
    state.deck = cards
    return True


def _draw_up_to_n_from_pile(state: GameState, n: int) -> list[Card]:
    drawn: list[Card] = []
    for _ in range(n):
        if not state.deck and not _reshuffle_discard_into_deck(state):
            break
        if not state.deck:
            break
        drawn.append(state.deck.pop())
    return drawn


def _resolve_draw(state: GameState, player_id: str) -> StepResult:
    if state.phase != GamePhase.DRAW:
        return _reject(state, player_id, DrawCards(), "not in draw phase")
    player = state.players[player_id]
    count = state.rules.empty_hand_draw_count if not player.hand else state.rules.draw_count
    drawn = _draw_up_to_n_from_pile(state, count)
    for card in drawn:
        player = player.add_to_hand(card)
    state.players[player_id] = player
    state.has_drawn = True
    state.phase = GamePhase.ACTION
    return StepResult(
        accepted=True,
        events=[
            GameEvent(
                type="cards_drawn",
                turn=state.turn,
                player=player_id,
                action="draw",
                result=str(len(drawn)),
                reason_summary=f"{player_id} drew {len(drawn)} cards.",
                payload={"card_ids": [card.id for card in drawn]},
            )
        ],
    )


def _resolve_discard(state: GameState, player_id: str, action: DiscardCard) -> StepResult:
    if state.phase != GamePhase.DISCARD:
        return _reject(state, player_id, action, "not in discard phase")
    if len(state.players[player_id].hand) <= state.rules.hand_limit:
        return _reject(state, player_id, action, "hand is already at or below limit")
    player, card = state.players[player_id].remove_from_hand(action.card_id)
    if card is None:
        return _reject(state, player_id, action, "card not in hand")
    state.players[player_id] = player
    state.discard.append(card)
    if len(player.hand) <= state.rules.hand_limit:
        state.advance_turn()
    return StepResult(
        accepted=True,
        events=[
            GameEvent(
                type="card_discarded",
                turn=state.turn,
                player=player_id,
                action="discard",
                card=card.name,
                reason_summary=f"{player_id} discarded {card.name}.",
            )
        ],
    )


def _resolve_payment(state: GameState, player_id: str, action: PayWithAssets) -> StepResult:
    pending = state.pending_payment
    if state.phase != GamePhase.PAYMENT or pending is None:
        return _reject(state, player_id, action, "no pending payment")
    if player_id != pending.payer_id:
        return _reject(state, player_id, action, "not payment payer")
    payer = state.players[pending.payer_id]
    if not is_legal_payment_selection(payer, tuple(action.card_ids), pending.amount):
        return _reject(state, player_id, action, "illegal payment selection")

    receiver = state.players[pending.receiver_id]
    paid: list[Card] = []
    for card_id in action.card_ids:
        payer, paid_card, source_color = payer.remove_asset(card_id)
        if paid_card is None:
            return _reject(state, player_id, action, "payment asset not found")
        paid.append(paid_card)
        receiver = _receive_paid_asset(receiver, paid_card, source_color)
    state.players[pending.payer_id] = payer
    state.players[pending.receiver_id] = receiver
    state.clear_pending_payment()
    return StepResult(
        accepted=True,
        events=[
            GameEvent(
                type="payment_made",
                turn=state.turn,
                player=player_id,
                target=pending.receiver_id,
                action="pay",
                result=str(sum(card.value for card in paid)),
                reason_summary=f"{player_id} paid {pending.receiver_id}.",
                payload={"card_ids": [card.id for card in paid], "owed": pending.amount},
            )
        ],
    )


def _receive_paid_asset(
    receiver: PlayerState, card: Card, source_color: PropertyColor | None
) -> PlayerState:
    if card.kind in {CardKind.PROPERTY, CardKind.WILD_PROPERTY}:
        color = source_color
        if color is None:
            color = card.playable_colors[0]
        return receiver.add_property(card, color)
    return receiver.add_to_bank(card)


def _resolve_rearrange(state: GameState, player_id: str, action: RearrangeProperty) -> StepResult:
    if state.rules.property_rearrange_timing.value == "never":
        return _reject(state, player_id, action, "property rearrange disabled")
    player = state.players[player_id]
    updated = player.set_property_color(action.card_id, action.color)
    if updated is None:
        return _reject(state, player_id, action, "property cannot use that color")
    state.players[player_id] = updated
    return StepResult(
        accepted=True,
        events=[
            GameEvent(
                type="property_rearranged",
                turn=state.turn,
                player=player_id,
                action="rearrange_property",
                result=action.color.value,
                reason_summary=f"{player_id} rearranged a property to {action.color.value}.",
            )
        ],
    )


def _resolve_rent(state: GameState, player_id: str, action: PlayRent) -> StepResult:
    cost = 2 if action.double_rent_card_id is not None else 1
    if not _can_take_counted_action(state, cost):
        return _reject(state, player_id, action, "action limit reached")
    player = state.players[player_id]
    card = _find_hand_card(player, action.card_id)
    if card is None or card.kind != CardKind.RENT:
        return _reject(state, player_id, action, "card is not a rent card in hand")
    if action.color is None or not _rent_card_can_charge(card, action.color):
        return _reject(state, player_id, action, "rent card cannot charge that color")
    target = state.players.get(action.target_player_id)
    if target is None:
        return _reject(state, player_id, action, "target player does not exist")
    amount = calculate_rent(player, action.color)
    if amount <= 0:
        return _reject(state, player_id, action, "no rent is owed for that color")

    player, rent_card = player.remove_from_hand(action.card_id)
    if rent_card is None:
        return _reject(state, player_id, action, "rent card not in hand")
    if action.double_rent_card_id is not None:
        player, double_card = player.remove_from_hand(action.double_rent_card_id)
        if double_card is None or double_card.action_subtype != ActionSubtype.DOUBLE_THE_RENT:
            return _reject(state, player_id, action, "double rent card not in hand")
        state.discard.append(double_card)
        amount *= 2
    state.players[player_id] = player
    state.discard.append(rent_card)
    state.actions_taken += cost
    state.pending_effect = PendingEffect(
        kind="payment",
        actor_id=player_id,
        target_id=action.target_player_id,
        source_card=rent_card,
        respond_player_id=action.target_player_id,
        amount=amount,
        color=action.color,
    )
    state.phase = GamePhase.RESPOND
    return StepResult(
        accepted=True,
        events=[
            GameEvent(
                type="rent_charged",
                turn=state.turn,
                player=player_id,
                target=target.id,
                action="play_rent",
                card=rent_card.name,
                result=str(amount),
                reason_summary=f"{player_id} charged {amount} rent to {target.id}.",
            )
        ],
    )


def _resolve_action_card(state: GameState, player_id: str, action: PlayActionCard) -> StepResult:
    if not _can_take_counted_action(state, 1):
        return _reject(state, player_id, action, "action limit reached")
    player = state.players[player_id]
    card = _find_hand_card(player, action.card_id)
    if card is None or card.kind != CardKind.ACTION or card.action_subtype is None:
        return _reject(state, player_id, action, "action card not in hand")
    subtype = card.action_subtype
    if subtype == ActionSubtype.PASS_GO:
        return _resolve_pass_go(state, player_id, action.card_id)
    if subtype in {ActionSubtype.HOUSE, ActionSubtype.HOTEL}:
        return _resolve_building(state, player_id, action.card_id, subtype, action.color)
    if subtype == ActionSubtype.DEBT_COLLECTOR:
        return _start_pending_effect(state, player_id, action, "payment", amount=5)
    if subtype == ActionSubtype.SLY_DEAL:
        return _start_pending_effect(state, player_id, action, "sly_deal")
    if subtype == ActionSubtype.FORCED_DEAL:
        return _start_pending_effect(state, player_id, action, "forced_deal")
    if subtype == ActionSubtype.DEAL_BREAKER:
        return _start_pending_effect(state, player_id, action, "deal_breaker")
    if subtype == ActionSubtype.ITS_MY_BIRTHDAY:
        return _resolve_its_my_birthday(state, player_id, action.card_id)
    return _reject(state, player_id, action, "unsupported action card")


def _resolve_its_my_birthday(state: GameState, player_id: str, card_id: str) -> StepResult:
    player, card = state.players[player_id].remove_from_hand(card_id)
    if card is None:
        return _reject(state, player_id, PlayActionCard(card_id), "card not in hand")
    state.players[player_id] = player
    state.discard.append(card)
    state.actions_taken += 1

    opponents = [pid for pid in state.player_order if pid != player_id]
    if not opponents:
        state.phase = state.next_phase_after_action()
        return StepResult(
            accepted=True,
            events=[
                GameEvent(
                    type="birthday_played",
                    turn=state.turn,
                    player=player_id,
                    action="its_my_birthday",
                    card=card.name,
                    reason_summary=f"{player_id} played {card.name} (no opponents).",
                )
            ],
        )

    payments = [
        PendingPayment(
            payer_id=oid,
            receiver_id=player_id,
            amount=2,
            reason=card.name,
        )
        for oid in opponents
    ]
    state.pending_payment = payments[0]
    state.pending_payment_queue = payments[1:]
    state.phase = GamePhase.PAYMENT
    first = state.pending_payment
    return StepResult(
        accepted=True,
        events=[
            GameEvent(
                type="birthday_played",
                turn=state.turn,
                player=player_id,
                action="its_my_birthday",
                card=card.name,
                reason_summary=f"{player_id} played {card.name}.",
            ),
            GameEvent(
                type="payment_requested",
                turn=state.turn,
                player=player_id,
                target=first.payer_id,
                action="payment",
                result=str(first.amount),
                reason_summary=f"{first.payer_id} owes {first.amount}.",
            ),
        ],
    )


def _resolve_pass_go(state: GameState, player_id: str, card_id: str) -> StepResult:
    player, card = state.players[player_id].remove_from_hand(card_id)
    if card is None:
        return _reject(state, player_id, PlayActionCard(card_id), "card not in hand")
    drawn = _draw_up_to_n_from_pile(state, 2)
    for drawn_card in drawn:
        player = player.add_to_hand(drawn_card)
    state.players[player_id] = player
    state.discard.append(card)
    state.actions_taken += 1
    state.phase = state.next_phase_after_action()
    return StepResult(
        accepted=True,
        events=[
            GameEvent(
                type="pass_go_played",
                turn=state.turn,
                player=player_id,
                action="pass_go",
                card=card.name,
                result=str(len(drawn)),
                reason_summary=f"{player_id} drew {len(drawn)} cards from Pass Go.",
            )
        ],
    )


def _resolve_building(
    state: GameState,
    player_id: str,
    card_id: str,
    subtype: ActionSubtype,
    color: PropertyColor | None,
) -> StepResult:
    if color is None:
        return _reject(state, player_id, PlayActionCard(card_id), "building color is required")
    player = state.players[player_id]
    if not player.can_build(color, subtype):
        return _reject(state, player_id, PlayActionCard(card_id, color=color), "cannot build there")
    player, card = player.remove_from_hand(card_id)
    if card is None:
        return _reject(state, player_id, PlayActionCard(card_id), "card not in hand")
    state.players[player_id] = player.add_property_attachment(card, color)
    state.discard.append(card)
    state.actions_taken += 1
    state.phase = state.next_phase_after_action()
    return StepResult(
        accepted=True,
        events=[
            GameEvent(
                type="building_played",
                turn=state.turn,
                player=player_id,
                action=subtype.value,
                card=card.name,
                result=color.value,
                reason_summary=f"{player_id} added {card.name} to {color.value}.",
            )
        ],
    )


def _start_pending_effect(
    state: GameState,
    player_id: str,
    action: PlayActionCard,
    kind: str,
    *,
    amount: int = 0,
) -> StepResult:
    if action.target_player_id is None:
        return _reject(state, player_id, action, "target player is required")
    if action.target_player_id not in state.players:
        return _reject(state, player_id, action, "target player does not exist")
    validation_error = _validate_effect_target(state, player_id, action, kind)
    if validation_error is not None:
        return _reject(state, player_id, action, validation_error)
    player, card = state.players[player_id].remove_from_hand(action.card_id)
    if card is None:
        return _reject(state, player_id, action, "card not in hand")
    state.players[player_id] = player
    state.discard.append(card)
    state.actions_taken += 1
    state.pending_effect = PendingEffect(
        kind=kind,
        actor_id=player_id,
        target_id=action.target_player_id,
        source_card=card,
        respond_player_id=action.target_player_id,
        amount=amount,
        color=action.color,
        target_card_id=action.target_card_id,
        offered_card_id=action.offered_card_id,
        requested_card_id=action.requested_card_id,
    )
    state.phase = GamePhase.RESPOND
    return StepResult(
        accepted=True,
        events=[
            GameEvent(
                type="effect_pending",
                turn=state.turn,
                player=player_id,
                target=action.target_player_id,
                action=kind,
                card=card.name,
                reason_summary=f"{player_id} played {card.name}.",
            )
        ],
    )


def _validate_effect_target(
    state: GameState, player_id: str, action: PlayActionCard, kind: str
) -> str | None:
    target = state.players[action.target_player_id or ""]
    actor = state.players[player_id]
    if kind == "sly_deal":
        if action.target_card_id is None:
            return "target property is required"
        if not any(
            card.id == action.target_card_id for card, _color in target.non_full_property_assets()
        ):
            return "target property is protected or missing"
    if kind == "forced_deal":
        if action.offered_card_id is None or action.requested_card_id is None:
            return "forced deal requires offered and requested properties"
        if not any(
            card.id == action.offered_card_id for card, _color in actor.non_full_property_assets()
        ):
            return "offered property is protected or missing"
        if not any(
            card.id == action.requested_card_id
            for card, _color in target.non_full_property_assets()
        ):
            return "requested property is protected or missing"
    if kind == "deal_breaker":
        if action.color is None or not target.is_full_set(action.color):
            return "target full set is required"
    return None


def _resolve_response(state: GameState, player_id: str, action: RespondJustSayNo) -> StepResult:
    pending = state.pending_effect
    if state.phase != GamePhase.RESPOND or pending is None:
        return _reject(state, player_id, action, "no pending response")
    if player_id != pending.respond_player_id:
        return _reject(state, player_id, action, "not response player")
    if not action.accept:
        if action.card_id is None:
            return _reject(state, player_id, action, "Just Say No card is required")
        player, card = state.players[player_id].remove_from_hand(action.card_id)
        if card is None or card.action_subtype != ActionSubtype.JUST_SAY_NO:
            return _reject(state, player_id, action, "Just Say No card not in hand")
        state.players[player_id] = player
        state.discard.append(card)
        pending.negated = not pending.negated
        if state.rules.allow_just_say_no_chain:
            pending.respond_player_id = (
                pending.actor_id if player_id == pending.target_id else pending.target_id
            )
            return StepResult(
                accepted=True,
                events=[
                    GameEvent(
                        type="just_say_no_played",
                        turn=state.turn,
                        player=player_id,
                        action="just_say_no",
                        card=card.name,
                        reason_summary=f"{player_id} played Just Say No.",
                    )
                ],
            )
        state.pending_effect = None
        state.phase = state.next_phase_after_action()
        return StepResult(accepted=True, events=[])

    if pending.negated:
        state.pending_effect = None
        state.phase = state.next_phase_after_action()
        return StepResult(
            accepted=True,
            events=[
                GameEvent(
                    type="effect_cancelled",
                    turn=state.turn,
                    player=player_id,
                    action=pending.kind,
                    reason_summary="The pending effect was cancelled.",
                )
            ],
        )
    events = _apply_pending_effect(state, pending)
    state.pending_effect = None
    return StepResult(accepted=True, events=events)


def _apply_pending_effect(state: GameState, pending: PendingEffect) -> list[GameEvent]:
    if pending.kind == "payment":
        state.set_pending_payment(
            payer_id=pending.target_id,
            receiver_id=pending.actor_id,
            amount=pending.amount,
            reason=pending.source_card.name,
        )
        return [
            GameEvent(
                type="payment_requested",
                turn=state.turn,
                player=pending.actor_id,
                target=pending.target_id,
                action="payment",
                result=str(pending.amount),
                reason_summary=f"{pending.target_id} owes {pending.amount}.",
            )
        ]
    if pending.kind == "sly_deal" and pending.target_card_id is not None:
        return [
            _transfer_property_card(
                state, pending.target_id, pending.actor_id, pending.target_card_id
            )
        ]
    if pending.kind == "forced_deal":
        if pending.offered_card_id is None or pending.requested_card_id is None:
            return []
        first = _transfer_property_card(
            state, pending.actor_id, pending.target_id, pending.offered_card_id
        )
        second = _transfer_property_card(
            state, pending.target_id, pending.actor_id, pending.requested_card_id
        )
        state.phase = state.next_phase_after_action()
        return [first, second]
    if pending.kind == "deal_breaker" and pending.color is not None:
        target = state.players[pending.target_id]
        actor = state.players[pending.actor_id]
        target, cards, attachments = target.remove_property_set(pending.color)
        for card in cards:
            actor = actor.add_property(card, pending.color)
        for attachment in attachments:
            actor = actor.add_property_attachment(attachment, pending.color)
        state.players[pending.target_id] = target
        state.players[pending.actor_id] = actor
        _check_winner(state, pending.actor_id)
        state.phase = state.next_phase_after_action()
        return [
            GameEvent(
                type="deal_breaker_resolved",
                turn=state.turn,
                player=pending.actor_id,
                target=pending.target_id,
                action="deal_breaker",
                result=pending.color.value,
                reason_summary=f"{pending.actor_id} took a full {pending.color.value} set.",
            )
        ]
    state.phase = state.next_phase_after_action()
    return []


def _transfer_property_card(
    state: GameState, from_player_id: str, to_player_id: str, card_id: str
) -> GameEvent:
    source = state.players[from_player_id]
    destination = state.players[to_player_id]
    source, card, color = source.remove_asset(card_id)
    if card is not None and color is not None:
        destination = destination.add_property(card, color)
    state.players[from_player_id] = source
    state.players[to_player_id] = destination
    _check_winner(state, to_player_id)
    state.phase = state.next_phase_after_action()
    return GameEvent(
        type="property_transferred",
        turn=state.turn,
        player=to_player_id,
        target=from_player_id,
        action="transfer_property",
        card=card.name if card else None,
        reason_summary=f"{to_player_id} received {card.name if card else card_id}.",
    )


def calculate_rent(player: PlayerState, color: PropertyColor) -> int:
    ladder = RENT_LADDER_BY_COLOR.get(color)
    if ladder is None:
        return 0
    property_count = len(player.properties.get(color, []))
    if property_count == 0:
        return 0
    amount = ladder[min(property_count, len(ladder)) - 1]
    attachments = player.property_attachments.get(color, [])
    if any(card.action_subtype == ActionSubtype.HOUSE for card in attachments):
        amount += 3
    if any(card.action_subtype == ActionSubtype.HOTEL for card in attachments):
        amount += 4
    return amount


def _rent_card_can_charge(card: Card, color: PropertyColor) -> bool:
    return PropertyColor.ANY in card.colors or color in card.colors


def _find_hand_card(player: PlayerState, card_id: str) -> Card | None:
    return next((card for card in player.hand if card.id == card_id), None)


def _can_take_counted_action(state: GameState, count: int) -> bool:
    return (
        state.phase == GamePhase.ACTION
        and state.actions_taken + count <= state.rules.actions_per_turn
    )


def _check_winner(state: GameState, player_id: str) -> None:
    if state.players[player_id].completed_set_count() >= state.rules.sets_to_win:
        state.winner_id = player_id
        state.phase = GamePhase.GAME_OVER


def _reject(state: GameState, player_id: str, action: Action, reason: str) -> StepResult:
    return StepResult(
        accepted=False,
        events=[
            GameEvent(
                type="action_rejected",
                turn=state.turn,
                player=player_id,
                action=type(action).__name__,
                result="rejected",
                reason_summary=reason,
            )
        ],
    )

from __future__ import annotations

from dataclasses import dataclass

from dbreaker.engine.cards import Card, PropertyColor
from dbreaker.engine.rules import GamePhase
from dbreaker.engine.state import GameState


@dataclass(frozen=True, slots=True)
class OpponentObservation:
    id: str
    name: str
    hand_size: int
    bank_value: int
    properties: dict[PropertyColor, tuple[Card, ...]]
    completed_sets: int


@dataclass(frozen=True, slots=True)
class PendingObservation:
    kind: str
    actor_id: str
    target_id: str
    respond_player_id: str | None
    amount: int
    source_card_name: str
    reason: str
    negated: bool = False


@dataclass(frozen=True, slots=True)
class Observation:
    player_id: str
    current_player_id: str
    active_player_id: str
    turn: int
    hand: list[Card]
    bank: list[Card]
    properties: dict[PropertyColor, list[Card]]
    opponents: dict[str, OpponentObservation]
    winner_id: str | None
    phase: GamePhase
    actions_taken: int
    actions_left: int
    discard_required: int
    pending: PendingObservation | None
    pending_summary: str | None
    omniscient: bool = False


def observation_for(state: GameState, player_id: str, *, omniscient: bool = False) -> Observation:
    player = state.players[player_id]
    opponents: dict[str, OpponentObservation] = {}
    for opponent_id, opponent in state.players.items():
        if opponent_id == player_id:
            continue
        opponents[opponent_id] = OpponentObservation(
            id=opponent.id,
            name=opponent.name,
            hand_size=len(opponent.hand),
            bank_value=sum(card.value for card in opponent.bank),
            properties={color: tuple(cards) for color, cards in opponent.properties.items()},
            completed_sets=opponent.completed_set_count(),
        )
    return Observation(
        player_id=player_id,
        current_player_id=state.current_player_id,
        active_player_id=state.active_player_id,
        turn=state.turn,
        hand=player.hand,
        bank=player.bank,
        properties=player.properties,
        opponents=opponents,
        winner_id=state.winner_id,
        phase=state.phase,
        actions_taken=state.actions_taken,
        actions_left=max(0, state.rules.actions_per_turn - state.actions_taken),
        discard_required=max(0, len(player.hand) - state.rules.hand_limit),
        pending=_pending_observation(state),
        pending_summary=_pending_summary(state),
        omniscient=omniscient,
    )


def _pending_summary(state: GameState) -> str | None:
    pending = _pending_observation(state)
    if pending is None:
        return None
    if pending.respond_player_id is not None:
        return (
            f"{pending.respond_player_id} must respond to {pending.source_card_name} "
            f"from {pending.actor_id}"
        )
    return f"{pending.actor_id} owes {pending.target_id} {pending.amount} for {pending.reason}"


def _pending_observation(state: GameState) -> PendingObservation | None:
    if state.pending_payment is not None:
        pending = state.pending_payment
        return PendingObservation(
            kind="payment",
            actor_id=pending.payer_id,
            target_id=pending.receiver_id,
            respond_player_id=None,
            amount=pending.amount,
            source_card_name=pending.reason,
            reason=pending.reason,
        )
    if state.pending_effect is not None:
        pending_effect = state.pending_effect
        return PendingObservation(
            kind=pending_effect.kind,
            actor_id=pending_effect.actor_id,
            target_id=pending_effect.target_id,
            respond_player_id=pending_effect.respond_player_id,
            amount=pending_effect.amount,
            source_card_name=pending_effect.source_card.name,
            reason=pending_effect.source_card.name,
            negated=pending_effect.negated,
        )
    return None

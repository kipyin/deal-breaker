from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dbreaker.engine.cards import Card, PropertyColor
from dbreaker.engine.player import PlayerState
from dbreaker.engine.rules import GamePhase, RuleConfig


@dataclass(slots=True)
class PendingPayment:
    payer_id: str
    receiver_id: str
    amount: int
    reason: str


@dataclass(slots=True)
class PendingEffect:
    kind: str
    actor_id: str
    target_id: str
    source_card: Card
    respond_player_id: str
    amount: int = 0
    color: PropertyColor | None = None
    target_card_id: str | None = None
    offered_card_id: str | None = None
    requested_card_id: str | None = None
    negated: bool = False


@dataclass(slots=True)
class GameState:
    players: dict[str, PlayerState]
    player_order: list[str]
    deck: list[Card]
    discard: list[Card] = field(default_factory=list)
    current_player_index: int = 0
    turn: int = 1
    actions_taken: int = 0
    phase: GamePhase = GamePhase.DRAW
    has_drawn: bool = False
    pending_payment: PendingPayment | None = None
    pending_payment_queue: list[PendingPayment] = field(default_factory=list)
    pending_effect: PendingEffect | None = None
    winner_id: str | None = None
    seed: int | None = None
    rules: RuleConfig = field(default_factory=RuleConfig.official)

    @property
    def current_player_id(self) -> str:
        return self.player_order[self.current_player_index]

    @property
    def active_player_id(self) -> str:
        if self.phase == GamePhase.PAYMENT and self.pending_payment is not None:
            return self.pending_payment.payer_id
        if self.phase == GamePhase.RESPOND and self.pending_effect is not None:
            return self.pending_effect.respond_player_id
        return self.current_player_id

    def advance_turn(self) -> None:
        self.current_player_index = (self.current_player_index + 1) % len(self.player_order)
        self.turn += 1
        self.actions_taken = 0
        self.has_drawn = False
        self.pending_payment = None
        self.pending_payment_queue.clear()
        self.pending_effect = None
        self.phase = GamePhase.DRAW

    def set_pending_payment(
        self, *, payer_id: str, receiver_id: str, amount: int, reason: str
    ) -> None:
        self.pending_payment = PendingPayment(
            payer_id=payer_id,
            receiver_id=receiver_id,
            amount=amount,
            reason=reason,
        )
        self.pending_payment_queue.clear()
        self.phase = GamePhase.PAYMENT

    def clear_pending_payment(self) -> None:
        if self.pending_payment_queue:
            self.pending_payment = self.pending_payment_queue.pop(0)
            self.phase = GamePhase.PAYMENT
        else:
            self.pending_payment = None
            self.phase = self.next_phase_after_action()

    def next_phase_after_action(self) -> GamePhase:
        if self.winner_id is not None:
            return GamePhase.GAME_OVER
        if self.actions_taken >= self.rules.actions_per_turn:
            return GamePhase.DISCARD
        return GamePhase.ACTION


def state_digest(state: GameState) -> tuple[Any, ...]:
    return (
        state.turn,
        state.current_player_id,
        state.active_player_id,
        state.phase.value,
        state.actions_taken,
        tuple(card.id for card in state.deck),
        tuple(card.id for card in state.discard),
        tuple(_player_digest(state.players[player_id]) for player_id in state.player_order),
        _pending_payment_digest(state.pending_payment),
        tuple(_pending_payment_digest(p) for p in state.pending_payment_queue),
        _pending_effect_digest(state.pending_effect),
        state.winner_id,
    )


def _player_digest(player: PlayerState) -> tuple[Any, ...]:
    return (
        player.id,
        tuple(card.id for card in player.hand),
        tuple(card.id for card in player.bank),
        tuple(
            (color.value, tuple(card.id for card in cards))
            for color, cards in sorted(player.properties.items(), key=lambda item: item[0].value)
        ),
        tuple(
            (color.value, tuple(card.id for card in cards))
            for color, cards in sorted(
                player.property_attachments.items(), key=lambda item: item[0].value
            )
        ),
    )


def _pending_payment_digest(pending: PendingPayment | None) -> tuple[Any, ...] | None:
    if pending is None:
        return None
    return (pending.payer_id, pending.receiver_id, pending.amount, pending.reason)


def _pending_effect_digest(pending: PendingEffect | None) -> tuple[Any, ...] | None:
    if pending is None:
        return None
    return (
        pending.kind,
        pending.actor_id,
        pending.target_id,
        pending.source_card.id,
        pending.respond_player_id,
        pending.amount,
        pending.color.value if pending.color is not None else None,
        pending.target_card_id,
        pending.offered_card_id,
        pending.requested_card_id,
        pending.negated,
    )

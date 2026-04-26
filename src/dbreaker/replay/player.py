from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dbreaker.engine.actions import Action, action_from_payload
from dbreaker.engine.cards import Card
from dbreaker.engine.game import Game
from dbreaker.engine.rules import GamePhase, RuleConfig
from dbreaker.engine.state import state_digest

Digest = tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class ReplayRecord:
    player_id: str
    action_payload: dict[str, Any]
    before_digest: Digest
    after_digest: Digest
    event_digests: tuple[Digest, ...]


def replay_actions(
    *,
    player_count: int,
    seed: int,
    actions: list[tuple[str, Action]],
) -> Game:
    game = Game.new(player_count=player_count, seed=seed)
    for player_id, action in actions:
        game.step(player_id, action)
    return game


def records_from_game(game: Game) -> list[ReplayRecord]:
    return [
        ReplayRecord(
            player_id=entry["player_id"],
            action_payload=entry["action_payload"],
            before_digest=tuple(entry["before_digest"]),
            after_digest=tuple(entry["after_digest"]),
            event_digests=tuple(tuple(digest) for digest in entry["event_digests"]),
        )
        for entry in game.action_log
    ]


def replay_records(
    *,
    player_count: int,
    seed: int,
    records: list[ReplayRecord],
    rules: RuleConfig | None = None,
    preset_hands: list[list[Card]] | None = None,
    initial_phase: GamePhase | None = None,
) -> Game:
    game = Game.new(
        player_count=player_count,
        seed=seed,
        rules=rules,
        preset_hands=preset_hands,
    )
    if initial_phase is not None:
        game.state.phase = initial_phase
    for record in records:
        if state_digest(game.state) != record.before_digest:
            raise ValueError("before digest mismatch")
        result = game.step(record.player_id, action_from_payload(record.action_payload))
        event_digests = tuple(event.digest() for event in result.events)
        if event_digests != record.event_digests:
            raise ValueError("event digest mismatch")
        if state_digest(game.state) != record.after_digest:
            raise ValueError("after digest mismatch")
    return game

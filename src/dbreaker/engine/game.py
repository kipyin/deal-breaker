from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dbreaker.engine.action_space import legal_actions as generate_legal_actions
from dbreaker.engine.actions import Action, action_to_payload
from dbreaker.engine.cards import Card
from dbreaker.engine.deck import shuffled_standard_deck
from dbreaker.engine.events import GameEvent
from dbreaker.engine.observation import Observation, observation_for
from dbreaker.engine.player import PlayerState
from dbreaker.engine.resolver import StepResult, resolve_action
from dbreaker.engine.rules import RuleConfig
from dbreaker.engine.state import GameState, state_digest


@dataclass(slots=True)
class Game:
    state: GameState
    event_log: list[GameEvent] = field(default_factory=list)
    action_log: list[dict[str, Any]] = field(default_factory=list)
    #: When False, :meth:`step` skips state digests, event log, and action log (faster RL rollouts).
    record_transitions: bool = True

    @classmethod
    def new(
        cls,
        *,
        player_count: int,
        seed: int | None = None,
        rules: RuleConfig | None = None,
        preset_hands: list[list[Card]] | None = None,
        record_transitions: bool = True,
    ) -> Game:
        if not 2 <= player_count <= 5:
            raise ValueError("player_count must be between 2 and 5")
        rule_config = rules or RuleConfig.official()
        deck = shuffled_standard_deck(seed)
        players: dict[str, PlayerState] = {}
        player_order = [f"P{index + 1}" for index in range(player_count)]
        for index, player_id in enumerate(player_order):
            if preset_hands is not None and index < len(preset_hands):
                hand = list(preset_hands[index])
            else:
                hand = [deck.pop() for _ in range(min(rule_config.starting_hand_size, len(deck)))]
            players[player_id] = PlayerState(id=player_id, name=player_id, hand=hand)
        return cls(
            state=GameState(
                players=players,
                player_order=player_order,
                deck=deck,
                seed=seed,
                rules=rule_config,
            ),
            record_transitions=record_transitions,
        )

    def legal_actions(self, player_id: str) -> list[Action]:
        return generate_legal_actions(self.state, player_id)

    @property
    def active_player_id(self) -> str:
        return self.state.active_player_id

    def step(self, player_id: str, action: Action) -> StepResult:
        if self.record_transitions:
            before = state_digest(self.state)
        result = resolve_action(self.state, player_id, action)
        if self.record_transitions:
            after = state_digest(self.state)
            self.event_log.extend(result.events)
            self.action_log.append(
                {
                    "player_id": player_id,
                    "action_payload": action_to_payload(action),
                    "before_digest": before,
                    "after_digest": after,
                    "event_digests": [event.digest() for event in result.events],
                }
            )
        return result

    def observation_for(self, player_id: str, *, omniscient: bool = False) -> Observation:
        return observation_for(self.state, player_id, omniscient=omniscient)

    def is_terminal(self) -> bool:
        return self.state.winner_id is not None

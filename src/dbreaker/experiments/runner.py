from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from dbreaker.engine.game import Game
from dbreaker.strategies.base import BaseStrategy

GameEndReason = Literal["winner", "max_turns", "aborted"]


@dataclass(frozen=True, slots=True)
class GameResult:
    game_id: str
    rankings: list[str]
    turns: int
    max_turns: int = 200
    ended_by: GameEndReason = "winner"
    abort_reason: str | None = None
    # Completed `game.step` calls in this self-play run.
    self_play_steps: int = 0


def _strategy_rankings(
    game: Game, player_strategy: dict[str, BaseStrategy]
) -> list[str]:
    order = sorted(
        game.state.player_order,
        key=lambda player_id: (
            game.state.winner_id is not None and player_id != game.state.winner_id,
            -game.state.players[player_id].completed_set_count(),
            -game.state.players[player_id].asset_value,
        ),
    )
    return [player_strategy[player_id].name for player_id in order]


def run_self_play_game(
    *,
    game_id: str,
    player_count: int,
    strategies: list[BaseStrategy],
    seed: int | None = None,
    max_turns: int = 200,
    max_self_play_steps: int = 30_000,
) -> GameResult:
    game = Game.new(player_count=player_count, seed=seed)
    player_strategy: dict[str, BaseStrategy] = {
        player_id: strategies[index % len(strategies)]
        for index, player_id in enumerate(game.state.player_order)
    }

    def finish(
        ended_by: GameEndReason,
        *,
        abort_reason: str | None = None,
        self_play_steps: int = 0,
    ) -> GameResult:
        return GameResult(
            game_id=game_id,
            rankings=_strategy_rankings(game, player_strategy),
            turns=game.state.turn,
            max_turns=max_turns,
            ended_by=ended_by,
            abort_reason=abort_reason,
            self_play_steps=self_play_steps,
        )

    steps_taken = 0
    while not game.is_terminal() and game.state.turn <= max_turns:
        if steps_taken >= max_self_play_steps:
            return finish(
                "aborted",
                abort_reason=(
                    f"exceeded self-play step limit ({max_self_play_steps}); "
                    f"turn={game.state.turn} phase={game.state.phase.value}"
                ),
                self_play_steps=steps_taken,
            )
        player_id = game.active_player_id
        legal_actions = game.legal_actions(player_id)
        if not legal_actions:
            return finish(
                "aborted",
                abort_reason="no legal actions for active player while game is not terminal",
                self_play_steps=steps_taken,
            )
        decision = player_strategy[player_id].choose_action(
            game.observation_for(player_id), legal_actions
        )
        step_result = game.step(player_id, decision.action)
        steps_taken += 1
        if not step_result.accepted:
            reason = (
                step_result.events[0].reason_summary
                if step_result.events
                else "unknown reject reason"
            )
            return finish("aborted", abort_reason=reason, self_play_steps=steps_taken)

    if game.is_terminal():
        return finish("winner", self_play_steps=steps_taken)
    return finish("max_turns", self_play_steps=steps_taken)

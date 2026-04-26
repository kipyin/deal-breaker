from __future__ import annotations

from dataclasses import dataclass

from dbreaker.engine.actions import EndTurn
from dbreaker.engine.game import Game
from dbreaker.strategies.base import BaseStrategy


@dataclass(frozen=True, slots=True)
class GameResult:
    game_id: str
    rankings: list[str]
    turns: int


def run_self_play_game(
    *,
    game_id: str,
    player_count: int,
    strategies: list[BaseStrategy],
    seed: int | None = None,
    max_turns: int = 200,
) -> GameResult:
    game = Game.new(player_count=player_count, seed=seed)
    player_strategy = {
        player_id: strategies[index % len(strategies)]
        for index, player_id in enumerate(game.state.player_order)
    }

    while not game.is_terminal() and game.state.turn <= max_turns:
        player_id = game.state.current_player_id
        legal_actions = game.legal_actions(player_id)
        if legal_actions:
            decision = player_strategy[player_id].choose_action(
                game.observation_for(player_id), legal_actions
            )
            game.step(player_id, decision.action)
        else:
            game.step(player_id, EndTurn())

    rankings = sorted(
        game.state.player_order,
        key=lambda player_id: (
            player_id != game.state.winner_id,
            -game.state.players[player_id].completed_set_count(),
            -game.state.players[player_id].asset_value,
        ),
    )
    strategy_rankings = [player_strategy[player_id].name for player_id in rankings]
    return GameResult(game_id=game_id, rankings=strategy_rankings, turns=game.state.turn)

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from dbreaker.experiments.elo import update_multiplayer_elo
from dbreaker.experiments.matrix import win_matrix
from dbreaker.experiments.metrics import summarize_results
from dbreaker.experiments.reports import TournamentReport
from dbreaker.experiments.runner import GameResult, run_self_play_game
from dbreaker.strategies.registry import create_strategy


@dataclass(frozen=True, slots=True)
class GameProgress:
    index: int
    total: int
    result: GameResult
    game_seed: int


def run_tournament(
    *,
    player_count: int,
    games: int,
    strategy_names: list[str],
    seed: int = 1,
    max_turns: int = 200,
    max_self_play_steps: int = 30_000,
    stalemate_turns: int | None = 25,
    on_game: Callable[[GameProgress], None] | None = None,
) -> TournamentReport:
    strategies = [create_strategy(name) for name in strategy_names]
    if not strategies:
        raise ValueError("at least one strategy is required")

    results: list[GameResult] = []
    ratings = {strategy.name: 1000.0 for strategy in strategies}
    games_with_winner = 0
    games_max_turn = 0
    games_stalemate = 0
    games_aborted = 0
    for index in range(games):
        rotated = [strategies[(index + offset) % len(strategies)] for offset in range(player_count)]
        result = run_self_play_game(
            game_id=f"game-{index + 1}",
            player_count=player_count,
            strategies=rotated,
            seed=seed + index,
            max_turns=max_turns,
            max_self_play_steps=max_self_play_steps,
            stalemate_turns=stalemate_turns,
        )
        if on_game is not None:
            on_game(
                GameProgress(
                    index=index,
                    total=games,
                    result=result,
                    game_seed=seed + index,
                )
            )
        results.append(result)
        if result.ended_by == "winner":
            games_with_winner += 1
            ratings = update_multiplayer_elo(ratings, result.rankings)
        elif result.ended_by == "max_turns":
            games_max_turn += 1
        elif result.ended_by == "stalemate":
            games_stalemate += 1
        else:
            games_aborted += 1

    return TournamentReport(
        summaries=summarize_results(results),
        ratings=ratings,
        matrix=win_matrix(results),
        games_with_winner=games_with_winner,
        games_max_turn=games_max_turn,
        games_stalemate=games_stalemate,
        games_aborted=games_aborted,
        max_turns_cap=max_turns,
    )

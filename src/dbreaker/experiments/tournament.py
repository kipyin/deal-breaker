from __future__ import annotations

from dbreaker.experiments.elo import update_multiplayer_elo
from dbreaker.experiments.matrix import win_matrix
from dbreaker.experiments.metrics import summarize_results
from dbreaker.experiments.reports import TournamentReport
from dbreaker.experiments.runner import GameResult, run_self_play_game
from dbreaker.strategies.registry import default_registry


def run_tournament(
    *,
    player_count: int,
    games: int,
    strategy_names: list[str],
    seed: int = 1,
) -> TournamentReport:
    registry = default_registry()
    strategies = [registry.create(name) for name in strategy_names]
    if not strategies:
        raise ValueError("at least one strategy is required")

    results: list[GameResult] = []
    ratings = {strategy.name: 1000.0 for strategy in strategies}
    for index in range(games):
        rotated = [strategies[(index + offset) % len(strategies)] for offset in range(player_count)]
        result = run_self_play_game(
            game_id=f"game-{index + 1}",
            player_count=player_count,
            strategies=rotated,
            seed=seed + index,
        )
        results.append(result)
        ratings = update_multiplayer_elo(ratings, result.rankings)

    return TournamentReport(
        summaries=summarize_results(results),
        ratings=ratings,
        matrix=win_matrix(results),
    )

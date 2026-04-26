from __future__ import annotations

from dbreaker.experiments.runner import GameResult


def win_matrix(results: list[GameResult]) -> dict[str, dict[str, float]]:
    wins: dict[str, dict[str, int]] = {}
    games: dict[str, dict[str, int]] = {}
    for result in results:
        if not result.rankings:
            continue
        winner = result.rankings[0]
        for strategy in result.rankings:
            wins.setdefault(winner, {}).setdefault(strategy, 0)
            games.setdefault(winner, {}).setdefault(strategy, 0)
        for opponent in result.rankings[1:]:
            wins.setdefault(winner, {}).setdefault(opponent, 0)
            games.setdefault(winner, {}).setdefault(opponent, 0)
            wins[winner][opponent] += 1
            games[winner][opponent] += 1
    return {
        winner: {
            opponent: wins[winner][opponent] / game_count
            for opponent, game_count in opponents.items()
            if game_count
        }
        for winner, opponents in games.items()
    }

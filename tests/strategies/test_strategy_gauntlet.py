"""Fast sanity check: strategies play short tournaments without errors."""

from __future__ import annotations

from dbreaker.experiments.tournament import run_tournament


def test_strategy_gauntlet_human_like_vs_random() -> None:
    report = run_tournament(
        player_count=2,
        games=6,
        strategy_names=["human_like", "random"],
        seed=13,
        max_turns=80,
    )
    total = (
        report.games_with_winner
        + report.games_max_turn
        + report.games_stalemate
        + report.games_aborted
    )
    assert total == 6
    assert "human_like" in report.summaries
    assert "random" in report.summaries

from __future__ import annotations

from dbreaker.experiments.tournament import GameProgress, run_tournament


def test_run_tournament_on_game_callback_and_seeds() -> None:
    seen: list[GameProgress] = []

    def on_game(p: GameProgress) -> None:
        seen.append(p)

    run_tournament(
        player_count=2,
        games=2,
        strategy_names=["basic", "basic"],
        seed=10,
        max_turns=30,
        max_self_play_steps=5_000,
        on_game=on_game,
    )

    assert len(seen) == 2
    assert seen[0].index == 0 and seen[0].total == 2
    assert seen[0].game_seed == 10
    assert seen[1].index == 1 and seen[1].total == 2
    assert seen[1].game_seed == 11
    assert seen[0].result.game_id == "game-1"
    assert seen[1].result.game_id == "game-2"
    for g in seen:
        assert len(g.result.rankings) == 2
        assert g.result.turns >= 1
        assert g.result.ended_by in ("winner", "max_turns", "stalemate", "aborted")


def test_run_tournament_max_turns_and_outcome_counts() -> None:
    report = run_tournament(
        player_count=2,
        games=3,
        strategy_names=["basic", "basic"],
        seed=42,
        max_turns=3,
        max_self_play_steps=5_000,
    )
    assert report.max_turns_cap == 3
    assert (
        report.games_with_winner
        + report.games_max_turn
        + report.games_stalemate
        + report.games_aborted
        == 3
    )
    assert "Outcomes:" in report.to_markdown()

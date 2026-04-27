from __future__ import annotations

import json

from dbreaker.experiments.benchmark import run_benchmark


def test_run_benchmark_outcome_counts_sum_to_games() -> None:
    report = run_benchmark(
        games=12,
        player_count=3,
        strategy_names=["basic", "random"],
        seed=7,
        max_turns=80,
        max_self_play_steps=10_000,
    )
    assert report.total_games == 12
    assert (
        report.games_winner
        + report.games_max_turn
        + report.games_stalemate
        + report.games_aborted
        == report.total_games
    )
    assert report.total_engine_steps >= report.total_games
    assert report.total_turns >= report.total_games


def test_run_benchmark_deterministic() -> None:
    a = run_benchmark(
        games=5,
        player_count=4,
        strategy_names=["basic", "basic", "basic", "basic"],
        seed=1,
        max_turns=100,
    )
    b = run_benchmark(
        games=5,
        player_count=4,
        strategy_names=["basic", "basic", "basic", "basic"],
        seed=1,
        max_turns=100,
    )
    assert a.total_engine_steps == b.total_engine_steps
    assert a.games_winner == b.games_winner
    assert a.games_max_turn == b.games_max_turn
    assert a.games_stalemate == b.games_stalemate
    assert a.games_aborted == b.games_aborted
    assert a.total_turns == b.total_turns
    assert a.average_steps_per_game == b.average_steps_per_game
    assert a.average_turns_per_game == b.average_turns_per_game


def test_run_benchmark_json_round_trip() -> None:
    report = run_benchmark(
        games=2,
        player_count=2,
        strategy_names=["basic", "basic"],
        seed=99,
        max_turns=20,
    )
    d = json.loads(report.to_json())
    assert d["total_games"] == 2
    assert d["base_seed"] == 99
    assert d["strategy_names"] == ["basic", "basic"]
    assert d["games_winner"] + d["games_max_turn"] + d["games_stalemate"] + d["games_aborted"] == 2
    assert d["stalemate_turns"] == 25


def test_run_benchmark_zero_games() -> None:
    report = run_benchmark(games=0, player_count=2, strategy_names=["basic"])
    assert report.total_games == 0
    assert report.total_engine_steps == 0
    assert report.games_winner == 0
    assert report.games_max_turn == 0
    assert report.games_stalemate == 0
    assert report.games_aborted == 0

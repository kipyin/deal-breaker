from __future__ import annotations

import json

import pytest

from dbreaker.experiments.benchmark import (
    NeuralTrainingBenchmarkReport,
    run_neural_training_benchmark,
)

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(torch is None, reason="torch is not installed")


def test_run_neural_training_benchmark_deterministic() -> None:
    torch.manual_seed(123)
    a = run_neural_training_benchmark(
        games=2,
        player_count=3,
        seed=42,
        max_turns=15,
        max_self_play_steps=500,
        update_epochs=1,
    )
    torch.manual_seed(123)
    b = run_neural_training_benchmark(
        games=2,
        player_count=3,
        seed=42,
        max_turns=15,
        max_self_play_steps=500,
        update_epochs=1,
    )
    assert a.training_steps == b.training_steps
    assert a.mean_reward == b.mean_reward
    assert a.rollout_seconds >= 0.0
    assert a.ppo_update_seconds >= 0.0
    # Total includes small overhead between rollout end, PPO start, and final accounting.
    assert a.elapsed_seconds + 1e-9 >= a.rollout_seconds + a.ppo_update_seconds


def test_run_neural_training_benchmark_json_round_trip() -> None:
    report = run_neural_training_benchmark(
        games=1,
        player_count=2,
        seed=7,
        max_turns=5,
        max_self_play_steps=100,
        update_epochs=1,
    )
    d = json.loads(report.to_json())
    assert d["games"] == 1
    assert d["player_count"] == 2
    assert d["seed"] == 7
    assert d["torch_seed"] is None
    assert d["training_steps"] == report.training_steps
    assert isinstance(report, NeuralTrainingBenchmarkReport)


def test_run_neural_training_benchmark_zero_games() -> None:
    report = run_neural_training_benchmark(games=0, player_count=2, seed=1)
    assert report.games == 0
    assert report.training_steps == 0
    assert report.mean_legal_actions_per_step == 0.0

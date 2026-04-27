from __future__ import annotations

from pathlib import Path

import pytest

from dbreaker.experiments.tournament import run_tournament
from dbreaker.ml.checkpoint import load_checkpoint, save_checkpoint
from dbreaker.ml.features import FEATURE_SCHEMA_VERSION
from dbreaker.ml.model import PolicyValueNetwork
from dbreaker.ml.trainer import PPOConfig, train_self_play
from dbreaker.ml.trajectory import collect_self_play_trajectory
from dbreaker.strategies.registry import create_strategy

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(torch is None, reason="torch is not installed")


def test_collect_self_play_trajectory_records_rewards_for_each_decision() -> None:
    model = PolicyValueNetwork()

    trajectory = collect_self_play_trajectory(
        model,
        player_count=2,
        seed=4,
        max_turns=1,
        max_self_play_steps=20,
    )

    assert trajectory.steps
    assert len(trajectory.rewards) == len(trajectory.steps)
    assert set(trajectory.rewards).issubset({-1.0, 0.0, 1.0})


def test_train_self_play_smoke_saves_loadable_checkpoint(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "selfplay.pt"

    stats = train_self_play(
        PPOConfig(
            games=1,
            player_count=2,
            max_turns=1,
            max_self_play_steps=20,
            update_epochs=1,
        ),
        checkpoint_out=checkpoint_path,
        seed=5,
    )
    checkpoint = load_checkpoint(checkpoint_path)

    assert stats.games == 1
    assert checkpoint.schema_version == FEATURE_SCHEMA_VERSION
    assert isinstance(checkpoint.model, PolicyValueNetwork)


def test_neural_strategy_checkpoint_is_usable_by_tournament(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "policy.pt"
    save_checkpoint(
        checkpoint_path,
        model=PolicyValueNetwork(),
        training_stats={"games": 0},
    )

    strategy = create_strategy(f"neural:{checkpoint_path}")
    report = run_tournament(
        player_count=2,
        games=1,
        strategy_names=[f"neural:{checkpoint_path}", "basic"],
        seed=6,
        max_turns=1,
        max_self_play_steps=30,
    )

    assert strategy.name.startswith("neural:")
    total_games = (
        report.games_with_winner
        + report.games_max_turn
        + report.games_stalemate
        + report.games_aborted
    )
    assert total_games == 1

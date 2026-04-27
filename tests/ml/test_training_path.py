from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from dbreaker.cli.app import app
from dbreaker.experiments.tournament import run_tournament
from dbreaker.ml.checkpoint import load_checkpoint, save_checkpoint
from dbreaker.ml.features import FEATURE_SCHEMA_VERSION
from dbreaker.ml.model import PolicyValueNetwork
from dbreaker.ml.trainer import PPOConfig, train_self_play
from dbreaker.ml.trajectory import (
    TrajectoryStep,
    collect_self_play_trajectory,
    sparse_terminal_rewards_for_steps,
)
from dbreaker.strategies.registry import create_strategy

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(torch is None, reason="torch is not installed")


def test_sparse_terminal_rewards_single_nonzero_per_player() -> None:
    from dbreaker.engine.actions import EndTurn
    from dbreaker.ml.features import (
        ACTION_FEATURE_DIM,
        FEATURE_SCHEMA_VERSION,
        OBSERVATION_FEATURE_DIM,
        EncodedActionBatch,
    )

    batch = EncodedActionBatch(
        schema_version=FEATURE_SCHEMA_VERSION,
        observation_features=(0.0,) * OBSERVATION_FEATURE_DIM,
        action_features=(tuple(0.0 for _ in range(ACTION_FEATURE_DIM)),),
        actions=(EndTurn(),),
    )
    steps = (
        TrajectoryStep("P1", batch, 0, 0.0, 0.0),
        TrajectoryStep("P2", batch, 0, 0.0, 0.0),
        TrajectoryStep("P1", batch, 0, 0.0, 0.0),
    )
    rewards = sparse_terminal_rewards_for_steps(
        steps,
        {"P1": 0.5, "P2": -0.5},
    )
    assert rewards == (0.0, -0.5, 0.5)


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


def test_rl_search_cli_trains_one_checkpoint(tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "rl-search-out"
    result = runner.invoke(
        app,
        [
            "rl-search",
            "--output-dir",
            str(out),
            "--players",
            "2",
            "--runs",
            "1",
            "--games-per-run",
            "1",
            "--seed",
            "7",
            "--max-turns",
            "1",
            "--max-self-play-steps",
            "30",
            "--update-epochs",
            "1",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    checkpoint = out / "2p" / "run-001.pt"
    manifest = out / "2p" / "run-001.json"
    assert checkpoint.is_file()
    assert manifest.is_file()


def test_rl_evaluate_cli_runs_tournament(tmp_path: Path) -> None:
    runner = CliRunner()
    ck = tmp_path / "policy.pt"
    train_result = runner.invoke(
        app,
        [
            "train",
            "--games",
            "1",
            "--players",
            "2",
            "--checkpoint-out",
            str(ck),
            "--max-turns",
            "1",
            "--max-self-play-steps",
            "30",
            "--update-epochs",
            "1",
            "--seed",
            "11",
        ],
    )
    assert train_result.exit_code == 0, train_result.stdout + train_result.stderr
    ev = runner.invoke(
        app,
        [
            "rl-evaluate",
            "--candidate",
            f"neural:{ck}",
            "--players",
            "2",
            "--eval-games",
            "1",
            "--max-turns",
            "1",
            "--max-self-play-steps",
            "40",
            "--seed",
            "12",
            "--baselines",
            "basic",
        ],
    )
    assert ev.exit_code == 0, ev.stdout + ev.stderr
    assert "basic" in ev.stdout

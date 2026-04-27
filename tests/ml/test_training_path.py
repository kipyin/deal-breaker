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
    metrics_path = tmp_path / "metrics.json"
    progress: list[tuple[int, int, str]] = []

    def on_game(i: int, trajectory: object) -> None:
        steps = getattr(trajectory, "steps", ())
        ended = getattr(trajectory, "ended_by", "")
        progress.append((i, len(steps), str(ended)))

    stats = train_self_play(
        PPOConfig(
            games=2,
            player_count=2,
            max_turns=1,
            max_self_play_steps=20,
            update_epochs=1,
        ),
        checkpoint_out=checkpoint_path,
        seed=5,
        on_game_complete=on_game,
        metrics_out=metrics_path,
    )
    checkpoint = load_checkpoint(checkpoint_path)

    assert stats.games == 2
    assert checkpoint.schema_version == FEATURE_SCHEMA_VERSION
    assert isinstance(checkpoint.model, PolicyValueNetwork)
    assert len(progress) == 2
    assert progress[0][0] == 0 and progress[1][0] == 1

    payload = stats.as_dict()
    assert payload.get("game_seed_offset") == 0
    assert "continued_from" not in payload
    assert "rollout_seconds" in payload
    assert "ppo_update_seconds" in payload
    assert "total_seconds" in payload
    assert "ended_by" in payload
    assert sum(payload["ended_by"].values()) == 2
    assert "per_game" in payload
    assert len(payload["per_game"]) == 2
    for row in payload["per_game"]:
        assert set(row.keys()) >= {"game_index", "learner_steps", "ended_by", "mean_reward"}
    if stats.steps > 0:
        assert payload.get("policy_loss") is not None
        assert payload.get("clip_fraction") is not None
    assert metrics_path.is_file()
    assert metrics_path.read_text(encoding="utf-8").strip().startswith("{")


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


def test_train_self_play_rejects_model_and_from_checkpoint_together() -> None:
    m = PolicyValueNetwork()
    with pytest.raises(ValueError, match="at most one"):
        train_self_play(
            PPOConfig(games=1, player_count=2, max_turns=1, max_self_play_steps=10, update_epochs=1),
            model=m,
            from_checkpoint=Path("nope.pt"),
        )


def test_from_checkpoint_sets_continued_from_in_stats(tmp_path: Path) -> None:
    base = tmp_path / "base.pt"
    train_self_play(
        PPOConfig(games=1, player_count=2, max_turns=1, max_self_play_steps=20, update_epochs=1),
        checkpoint_out=base,
        seed=3,
    )
    out = tmp_path / "out.pt"
    stats = train_self_play(
        PPOConfig(games=1, player_count=2, max_turns=1, max_self_play_steps=20, update_epochs=1),
        checkpoint_out=out,
        seed=3,
        from_checkpoint=base,
        game_seed_offset=1,
    )
    assert stats.continued_from == str(base)
    d = stats.as_dict()
    assert d["continued_from"] == str(base)
    assert d["game_seed_offset"] == 1


def test_game_seed_offset_changes_self_play_seed(tmp_path: Path) -> None:
    """Per-game seed is seed + game_index + offset; offset 0 vs 1 should diverge trajectories."""
    a = tmp_path / "a.pt"
    b = tmp_path / "b.pt"
    train_self_play(
        PPOConfig(games=1, player_count=2, max_turns=1, max_self_play_steps=25, update_epochs=1),
        checkpoint_out=a,
        seed=10,
        game_seed_offset=0,
    )
    train_self_play(
        PPOConfig(games=1, player_count=2, max_turns=1, max_self_play_steps=25, update_epochs=1),
        checkpoint_out=b,
        seed=10,
        game_seed_offset=1,
    )
    sa = load_checkpoint(a).model.state_dict()
    sb = load_checkpoint(b).model.state_dict()
    assert any(
        not torch.equal(sa[k], sb[k]) for k in sa.keys()  # type: ignore[union-attr]
    )


def test_train_cli_from_checkpoint_and_game_seed_offset(tmp_path: Path) -> None:
    runner = CliRunner()
    base = tmp_path / "base.pt"
    r0 = runner.invoke(
        app,
        [
            "train",
            "--games",
            "1",
            "--players",
            "2",
            "--checkpoint-out",
            str(base),
            "--max-turns",
            "1",
            "--max-self-play-steps",
            "25",
            "--update-epochs",
            "1",
            "--seed",
            "42",
        ],
    )
    assert r0.exit_code == 0, r0.stdout + r0.stderr
    out = tmp_path / "out.pt"
    r1 = runner.invoke(
        app,
        [
            "train",
            "--games",
            "1",
            "--players",
            "2",
            "--checkpoint-out",
            str(out),
            "--from-checkpoint",
            str(base),
            "--game-seed-offset",
            "5",
            "--max-turns",
            "1",
            "--max-self-play-steps",
            "25",
            "--update-epochs",
            "1",
            "--seed",
            "42",
        ],
    )
    assert r1.exit_code == 0, r1.stdout + r1.stderr
    assert out.is_file()


def test_training_job_request_resume_and_seed_offset_fields() -> None:
    from dbreaker.web.schemas import TrainingJobRequest

    body = TrainingJobRequest(
        player_count=2,
        games=1,
        resume_from_checkpoint_id="ckpt_x",
        game_seed_offset=100,
    )
    d = body.model_dump()
    assert d["resume_from_checkpoint_id"] == "ckpt_x"
    assert d["game_seed_offset"] == 100

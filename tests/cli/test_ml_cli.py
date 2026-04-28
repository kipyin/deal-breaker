from __future__ import annotations

from typer.testing import CliRunner

from dbreaker.cli.app import app


def test_train_and_evaluate_commands_are_registered() -> None:
    runner = CliRunner()

    train_help = runner.invoke(app, ["train", "--help"])
    evaluate_help = runner.invoke(app, ["evaluate", "--help"])
    rl_search_help = runner.invoke(app, ["rl-search", "--help"])
    rl_eval_help = runner.invoke(app, ["rl-evaluate", "--help"])

    assert train_help.exit_code == 0
    assert "--checkpoint-out" in (train_help.stdout + train_help.stderr)
    assert "--from-checkpoint" in (train_help.stdout + train_help.stderr)
    assert "--game-seed-offset" in (train_help.stdout + train_help.stderr)
    assert "--gamma" in (train_help.stdout + train_help.stderr)
    assert "--opponent-mix" in (train_help.stdout + train_help.stderr)
    assert "--rollout-batch-games" in (train_help.stdout + train_help.stderr)
    assert evaluate_help.exit_code == 0
    assert "--candidate" in (evaluate_help.stdout + evaluate_help.stderr)
    assert rl_search_help.exit_code == 0
    assert "--output-dir" in (rl_search_help.stdout + rl_search_help.stderr)
    assert "--rollout-batch-games" in (rl_search_help.stdout + rl_search_help.stderr)
    assert rl_eval_help.exit_code == 0
    assert "--eval-games" in (rl_eval_help.stdout + rl_eval_help.stderr)
    assert "--champions" in (rl_eval_help.stdout + rl_eval_help.stderr)

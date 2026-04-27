from __future__ import annotations

from typer.testing import CliRunner

from dbreaker.cli.app import app


def test_train_and_evaluate_commands_are_registered() -> None:
    runner = CliRunner()

    train_help = runner.invoke(app, ["train", "--help"])
    evaluate_help = runner.invoke(app, ["evaluate", "--help"])

    assert train_help.exit_code == 0
    assert "--checkpoint-out" in (train_help.stdout + train_help.stderr)
    assert evaluate_help.exit_code == 0
    assert "--candidate" in (evaluate_help.stdout + evaluate_help.stderr)

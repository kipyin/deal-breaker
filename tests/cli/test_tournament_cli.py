from __future__ import annotations

from typer.testing import CliRunner

from dbreaker.cli.app import app


def test_tournament_command_accepts_max_turn_and_max_steps() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "tournament",
            "--games",
            "1",
            "--players",
            "2",
            "--strategies",
            "basic",
            "--max-turns",
            "12",
            "--max-self-play-steps",
            "8000",
        ],
    )
    assert result.exit_code == 0
    assert "Outcomes:" in result.stdout
    assert "cap 12" in result.stdout

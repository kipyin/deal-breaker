from __future__ import annotations

from typer.testing import CliRunner

from dbreaker.cli.app import app


def test_root_help_lists_global_verbose() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = (result.stdout or "") + (result.stderr or "")
    assert "--verbose" in out
    assert " -v," in out or "\n  -v," in out or " -v " in out


def test_benchmark_info_log_on_stderr_stdout_uncluttered() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "benchmark",
            "--games",
            "0",
            "--players",
            "2",
            "--strategies",
            "basic,basic",
            "--output",
            "text",
        ],
    )
    assert result.exit_code == 0
    assert "total_games=0" in (result.stdout or "")
    err = result.stderr or ""
    assert "INFO" in err
    assert "benchmark games=" in err


def test_global_verbose_emits_debug_line() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "-v",
            "benchmark",
            "--games",
            "0",
            "--players",
            "2",
            "--strategies",
            "basic,basic",
            "--output",
            "text",
        ],
    )
    assert result.exit_code == 0
    err = result.stderr or ""
    assert "DEBUG" in err
    assert "CLI debug logging enabled" in err


def test_tournament_local_verbose_prints_game_progress() -> None:
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
            "-v",
        ],
    )
    assert result.exit_code == 0
    assert "Outcomes:" in (result.stdout or "")
    err = result.stderr or ""
    assert "game-1" in err


def test_global_verbose_alone_does_not_enable_tournament_progress_lines() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "-v",
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
    err = result.stderr or ""
    assert "DEBUG" in err
    assert "game-1" not in err

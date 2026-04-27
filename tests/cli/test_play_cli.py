from __future__ import annotations

import json

from typer.testing import CliRunner

from dbreaker.cli.app import app


def test_play_help_mentions_scripted_mode_and_examples() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["play", "--help"])
    assert result.exit_code == 0, result.stdout
    out = (result.stdout or "") + (result.stderr or "")
    assert "--commands" in out
    assert "--output" in out
    assert "Non-interactive" in out or "non-interactive" in out.lower()
    assert "printf" in out or "uv run dbreaker play --commands" in out


def test_play_invalid_output_exits_2() -> None:
    runner = CliRunner()
    r2 = runner.invoke(
        app,
        [
            "play",
            "--commands",
            "-",
            "--output",
            "nope",
        ],
    )
    assert r2.exit_code == 2
    assert "output" in (r2.stdout + r2.stderr).lower()


def test_play_scripted_end_illegal_in_draw_phase() -> None:
    """DRAW phase only allows 'draw' — 'end' must fail fast with legal_actions."""
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "play",
            "--seed",
            "1",
            "--players",
            "2",
            "--commands",
            "-",
            "--output",
            "text",
        ],
        input="end\n",
    )
    assert result.exit_code == 1
    err = result.stderr or ""
    assert "Error" in err
    assert "legal" in err.lower() or "Legal" in err
    assert "Example" in err or "example" in err


def test_play_scripted_jsonl_legal_state_and_error_object() -> None:
    """First line is illegal; JSON error includes legal_actions and example hint."""
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "play",
            "--seed",
            "1",
            "--players",
            "2",
            "--commands",
            "-",
            "--output",
            "jsonl",
        ],
        input="end\n",
    )
    assert result.exit_code == 1
    lines = [ln for ln in (result.stdout or "").splitlines() if ln.strip()]
    assert lines, "expected JSONL before error"
    first = json.loads(lines[0])
    assert first["type"] == "legal_state"
    assert first["player"] == "P1"
    assert "legal_actions" in first and first["legal_actions"]
    err_line = json.loads(lines[-1])
    assert err_line["type"] == "error"
    assert "example" in err_line
    assert "legal_actions" in err_line or err_line.get("message")


def test_play_scripted_valid_draw_produces_step() -> None:
    """One legal 'draw' applies; then the run stops needing more P1 input (EOF)."""
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "play",
            "--seed",
            "1",
            "--players",
            "2",
            "--commands",
            "-",
            "--output",
            "text",
        ],
        input="draw\n",
    )
    assert result.exit_code == 1
    out = result.stdout or ""
    assert "P1> draw" in out
    err = result.stderr or ""
    assert "end of command stream" in err.lower() or "command stream" in err.lower()

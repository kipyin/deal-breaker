from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from dbreaker.cli import app as cli_app


def test_api_help_describes_backend_only_command() -> None:
    runner = CliRunner()

    result = runner.invoke(cli_app.app, ["api", "--help"])

    assert result.exit_code == 0
    out = result.stdout + result.stderr
    assert "FastAPI" in out
    assert "backend" in out.lower() or "api" in out.lower()
    assert "--host" in out
    assert "--port" in out


def test_web_help_describes_full_app_launcher() -> None:
    runner = CliRunner()

    result = runner.invoke(cli_app.app, ["web", "--help"])

    assert result.exit_code == 0
    out = result.stdout + result.stderr
    assert "FastAPI" in out
    assert "Vite" in out
    assert "--frontend-host" in out
    assert "--frontend-port" in out
    assert "--no-open" in out


def test_web_command_delegates_to_full_stack_launcher(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run_full_web_stack(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(cli_app, "_run_full_web_stack", fake_run_full_web_stack)
    runner = CliRunner()

    result = runner.invoke(
        cli_app.app,
        [
            "web",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
            "--frontend-host",
            "127.0.0.1",
            "--frontend-port",
            "5174",
            "--data-dir",
            "tmp-data",
            "--artifacts-dir",
            "tmp-artifacts",
            "--no-open",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "host": "0.0.0.0",
            "port": 9000,
            "frontend_host": "127.0.0.1",
            "frontend_port": 5174,
            "data_dir": Path("tmp-data"),
            "artifacts_dir": Path("tmp-artifacts"),
            "open_browser": False,
        }
    ]


def test_api_command_delegates_to_backend_runner(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run_api_server(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(cli_app, "_run_api_server", fake_run_api_server)
    runner = CliRunner()

    result = runner.invoke(
        cli_app.app,
        [
            "api",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
            "--data-dir",
            "tmp-data",
            "--artifacts-dir",
            "tmp-artifacts",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "host": "0.0.0.0",
            "port": 9000,
            "data_dir": Path("tmp-data"),
            "artifacts_dir": Path("tmp-artifacts"),
        }
    ]

from __future__ import annotations

from pathlib import Path

import typer

from dbreaker.cli.play import run_interactive_play
from dbreaker.experiments.tournament import run_tournament
from dbreaker.replay.log_store import read_events

app = typer.Typer(help="Monopoly Deal AI strategy research platform.")


@app.command()
def play(
    players: int = typer.Option(3, min=2, max=5, help="Total human + AI players."),
    ai_strategy: str = typer.Option("basic", help="Strategy for AI opponents."),
) -> None:
    """Play a terminal game against AI opponents."""
    run_interactive_play(players=players, ai_strategy=ai_strategy)


@app.command()
def tournament(
    players: int = typer.Option(4, min=2, max=5),
    games: int = typer.Option(100),
    strategies: str = typer.Option("random,basic,aggressive,defensive"),
) -> None:
    """Run an AI self-play tournament."""
    report = run_tournament(
        player_count=players,
        games=games,
        strategy_names=[name.strip() for name in strategies.split(",") if name.strip()],
    )
    typer.echo(report.to_markdown())


@app.command()
def replay(path: Path) -> None:
    """Print events from a JSONL replay file."""
    for event in read_events(path):
        typer.echo(f"{event.turn}: {event.type} {event.reason_summary}")

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import Annotated, Literal

import typer

from dbreaker.cli.play import run_interactive_play, run_scripted_play
from dbreaker.experiments.benchmark import run_benchmark
from dbreaker.experiments.tournament import GameProgress, run_tournament
from dbreaker.replay.log_store import read_events

app = typer.Typer(help="Monopoly Deal AI strategy research platform.")


def _format_tournament_game_line(p: GameProgress, detail: bool) -> str:
    r = p.result
    if r.ended_by == "winner":
        lead = f"winner={r.rankings[0]}"
    elif r.ended_by == "max_turns":
        lead = f"outcome=max_turns first={r.rankings[0]}"
    elif r.ended_by == "stalemate":
        lead = f"outcome=stalemate first={r.rankings[0]}"
    else:
        reason = (r.abort_reason or "unknown").replace("\n", " ")
        lead = f"outcome=aborted reason={reason}"
    base = f"{p.index + 1}/{p.total} {r.game_id} {lead} turns={r.turns}"
    if not detail:
        return base
    order = ",".join(r.rankings)
    return f"{base} seed={p.game_seed} steps={r.self_play_steps} rankings={order}"


@app.command()
def play(
    players: int = typer.Option(3, min=2, max=5, help="Total human + AI players."),
    ai_strategy: str = typer.Option("basic", help="Strategy for AI opponents."),
    commands: Annotated[
        Path | None,
        typer.Option(
            "--commands",
            help=(
                "Read human shortcut lines from this file, or '-' for stdin (non-interactive). "
                "Each line is one `parse_command` (see `dbreaker play --help` Examples). "
                "Lines starting with # and blank lines are skipped."
            ),
            show_default=False,
        ),
    ] = None,
    output: str = typer.Option(
        "text",
        "--output",
        help=(
            "With --commands: 'text' for human-readable logs, "
            "'jsonl' for one JSON object per line."
        ),
    ),
    seed: int | None = typer.Option(
        None,
        "--seed",
        help="RNG seed for shuffling the deck (reproducible scripted runs).",
    ),
) -> None:
    """Play a terminal game against AI opponents (interactive), or a scripted run via --commands.

    Examples (interactive, default):

        uv run dbreaker play
        uv run dbreaker play --players 3 --ai-strategy basic

    Non-interactive (agents / scripts) — P1 is human; one shortcut command per P1 turn:

        printf 'draw\\nend\\n' | uv run dbreaker play --commands - --output text
        uv run dbreaker play --commands ./moves.txt --output jsonl
        uv run dbreaker play --seed 42 --players 2 --commands -  # reproducible
    """
    out = output.lower().strip()
    if out not in {"text", "jsonl"}:
        typer.secho(
            f"Error: --output must be 'text' or 'jsonl', got {output!r}.",
            err=True,
        )
        raise typer.Exit(2)
    mode: Literal["text", "jsonl"] = "text" if out == "text" else "jsonl"
    if commands is None:
        run_interactive_play(players=players, ai_strategy=ai_strategy)
        return
    path = str(commands)
    if path == "-":
        code = run_scripted_play(
            players=players,
            ai_strategy=ai_strategy,
            command_source=sys.stdin,
            output=mode,
            seed=seed,
        )
    else:
        with open(path, encoding="utf-8") as f:
            code = run_scripted_play(
                players=players,
                ai_strategy=ai_strategy,
                command_source=f,
                output=mode,
                seed=seed,
            )
    raise typer.Exit(code)


@app.command()
def tournament(
    players: int = typer.Option(4, min=2, max=5),
    games: int = typer.Option(100),
    strategies: str = typer.Option("random,basic,aggressive,defensive"),
    seed: int = typer.Option(1, help="Base RNG seed; game n uses seed + n − 1."),
    max_turns: int = typer.Option(
        200,
        "--max-turns",
        min=1,
        help="Stop self-play after this many full turns; games may end in a draw ranking.",
    ),
    max_self_play_steps: int = typer.Option(
        30_000,
        "--max-self-play-steps",
        min=1,
        help="Hard cap on engine step() calls per game (safety: avoids pathological long runs).",
    ),
    stalemate_turns: int = typer.Option(
        25,
        "--stalemate-turns",
        min=0,
        help="End a game as stalemate if max completed sets and total asset value do not increase "
        "for this many full turns. 0 disables (only max-turns cap ends non-wins).",
    ),
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="Per-game progress on stderr: -v compact, -vv with seed and full rank order.",
    ),
    log_path: Annotated[
        Path | None,
        typer.Option(
            "--log",
            help="Append one progress line per game (compact if not -vv).",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Run an AI self-play tournament."""
    need_lines = bool(log_path) or verbose >= 1
    line_detail = min(verbose, 2) >= 2

    def on_game(p: GameProgress) -> None:
        line = _format_tournament_game_line(p, detail=line_detail)
        if log_path is not None:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        if verbose >= 1:
            typer.secho(line, err=True)

    on_cb = on_game if need_lines else None

    report = run_tournament(
        player_count=players,
        games=games,
        strategy_names=[name.strip() for name in strategies.split(",") if name.strip()],
        seed=seed,
        max_turns=max_turns,
        max_self_play_steps=max_self_play_steps,
        stalemate_turns=stalemate_turns,
        on_game=on_cb,
    )
    typer.echo(report.to_markdown())


@app.command()
def train(
    games: int = typer.Option(10, min=1, help="Self-play games to collect before checkpointing."),
    players: int = typer.Option(4, "--players", min=2, max=5, help="Players per training game."),
    checkpoint_out: Annotated[
        Path,
        typer.Option("--checkpoint-out", help="Path to write a neural checkpoint."),
    ] = Path("checkpoints/selfplay.pt"),
    seed: int = typer.Option(1, help="Base RNG seed; game n uses seed + n - 1."),
    max_turns: int = typer.Option(200, "--max-turns", min=1),
    max_self_play_steps: int = typer.Option(30_000, "--max-self-play-steps", min=1),
    update_epochs: int = typer.Option(2, "--update-epochs", min=1),
) -> None:
    """Train a checkpoint-backed neural policy with small PPO-style self-play updates."""
    try:
        trainer_module = import_module("dbreaker.ml.trainer")
        config = trainer_module.PPOConfig(
            games=games,
            player_count=players,
            max_turns=max_turns,
            max_self_play_steps=max_self_play_steps,
            update_epochs=update_epochs,
        )
        stats = trainer_module.train_self_play(config, checkpoint_out=checkpoint_out, seed=seed)
    except ImportError as exc:
        typer.secho(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(
        f"trained games={stats.games} steps={stats.steps} "
        f"mean_reward={stats.mean_reward:.3f} checkpoint={checkpoint_out}"
    )


@app.command()
def evaluate(
    candidate: str = typer.Option(
        ...,
        "--candidate",
        help="Candidate strategy, e.g. neural:path.pt.",
    ),
    baseline: str = typer.Option("basic", "--baseline", help="Baseline strategy name or spec."),
    games: int = typer.Option(20, min=1),
    players: int = typer.Option(2, "--players", min=2, max=5),
    seed: int = typer.Option(1),
    max_turns: int = typer.Option(200, "--max-turns", min=1),
    max_self_play_steps: int = typer.Option(30_000, "--max-self-play-steps", min=1),
) -> None:
    """Evaluate a candidate strategy against a baseline using tournament reporting."""
    try:
        report = run_tournament(
            player_count=players,
            games=games,
            strategy_names=[candidate, baseline],
            seed=seed,
            max_turns=max_turns,
            max_self_play_steps=max_self_play_steps,
        )
    except ImportError as exc:
        typer.secho(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(report.to_markdown())


@app.command()
def benchmark(
    games: int = typer.Option(200, min=0, help="Number of self-play games to run."),
    players: int = typer.Option(4, "--players", min=2, max=5, help="Players per table."),
    strategies: str = typer.Option(
        "basic,basic,basic,basic",
        "--strategies",
        help="Comma-separated strategy names; seats rotate by game index (see tournament).",
    ),
    seed: int = typer.Option(1, help="Base seed; game n uses seed + n − 1 (same as tournament)."),
    max_turns: int = typer.Option(
        200,
        "--max-turns",
        min=1,
        help="Stop self-play after this many full turns; games may end in a draw ranking.",
    ),
    max_self_play_steps: int = typer.Option(
        30_000,
        "--max-self-play-steps",
        min=1,
        help="Hard cap on engine step() calls per game.",
    ),
    stalemate_turns: int = typer.Option(
        25,
        "--stalemate-turns",
        min=0,
        help="Stalemate when no (sets, total asset) progress for this many full turns. 0 disables.",
    ),
    output: str = typer.Option(
        "text",
        "--output",
        help=(
            "'text' for one key=value per line, "
            "'json' for a single JSON object (script-friendly)."
        ),
    ),
) -> None:
    """Measure simulator throughput (games/sec, steps/sec) and outcome counts for self-play.

    Profiling example (saves a profile; inspect with ``python -m pstats``)::

        uv run python -m cProfile -o .tmp/dbreaker-benchmark.prof \
            -m dbreaker.cli.app benchmark --games 500

    """
    out = output.lower().strip()
    if out not in {"text", "json"}:
        typer.secho(
            f"Error: --output must be 'text' or 'json', got {output!r}.",
            err=True,
        )
        raise typer.Exit(2)
    names = [name.strip() for name in strategies.split(",") if name.strip()]
    if not names:
        typer.secho("Error: --strategies must list at least one strategy name.", err=True)
        raise typer.Exit(2)
    report = run_benchmark(
        games=games,
        player_count=players,
        strategy_names=names,
        seed=seed,
        max_turns=max_turns,
        max_self_play_steps=max_self_play_steps,
        stalemate_turns=stalemate_turns,
    )
    if out == "json":
        typer.echo(report.to_json())
    else:
        for line in report.to_text_lines():
            typer.echo(line)


@app.command()
def replay(path: Path) -> None:
    """Print events from a JSONL replay file."""
    for event in read_events(path):
        typer.echo(f"{event.turn}: {event.type} {event.reason_summary}")


if __name__ == "__main__":
    app()

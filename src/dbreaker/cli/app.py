from __future__ import annotations

import subprocess
import sys
import time
import webbrowser
from importlib import import_module
from pathlib import Path
from typing import Annotated, Literal

import typer

from dbreaker.cli.play import run_interactive_play, run_scripted_play
from dbreaker.experiments.benchmark import run_benchmark, run_neural_training_benchmark
from dbreaker.experiments.rl_search import (
    EvaluationConfig,
    RLSearchConfig,
    evaluate_candidate,
    promote_champion,
    run_rl_search,
)
from dbreaker.experiments.tournament import GameProgress, run_tournament
from dbreaker.replay.log_store import read_events

app = typer.Typer(help="Monopoly Deal AI strategy research platform.")


def _parse_comma_ints(spec: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in spec.split(",") if part.strip())


def _parse_comma_strs(spec: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in spec.split(",") if part.strip())


def _promotion_checkpoint(candidate: str, override: str | None) -> str:
    if override:
        return override
    if candidate.startswith("neural:"):
        return candidate.removeprefix("neural:")
    return candidate


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
    seed: int = typer.Option(
        1,
        help="Base RNG seed; game i uses seed + i + game_seed_offset (0-based i).",
    ),
    max_turns: int = typer.Option(200, "--max-turns", min=1),
    max_self_play_steps: int = typer.Option(30_000, "--max-self-play-steps", min=1),
    update_epochs: int = typer.Option(2, "--update-epochs", min=1),
    gamma: float = typer.Option(
        0.99,
        "--gamma",
        min=0.0,
        max=1.0,
        help="Discount on sparse terminal rewards for value targets.",
    ),
    opponent_mix: float = typer.Option(
        0.0,
        "--opponent-mix",
        min=0.0,
        max=1.0,
        help=(
            "Probability per game of training against heuristics / champion "
            "instead of pure self-play."
        ),
    ),
    opponents: str = typer.Option(
        "basic,aggressive,defensive,set_completion",
        "--opponents",
        help="Comma-separated heuristic strategies sampled when opponent mixing is active.",
    ),
    champion: Annotated[
        Path | None,
        typer.Option(
            "--champion",
            help="Optional checkpoint path added to the opponent pool when mixing.",
        ),
    ] = None,
    from_checkpoint: Annotated[
        Path | None,
        typer.Option(
            "--from-checkpoint",
            help="Load policy weights from this checkpoint (continuation training).",
        ),
    ] = None,
    game_seed_offset: int = typer.Option(
        0,
        "--game-seed-offset",
        min=0,
        help=(
            "Added to each game's RNG seed. When splitting into batches, set to the "
            "cumulative number of games from prior runs (same --seed) to avoid replaying "
            "the same self-play seeds."
        ),
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Print one line per self-play game (steps, outcome, mean reward).",
    ),
    metrics_out: Annotated[
        Path | None,
        typer.Option(
            "--metrics-out",
            help="Write extended training metrics and per-game rows as JSON.",
        ),
    ] = None,
) -> None:
    """Train a checkpoint-backed neural policy with small PPO-style self-play updates."""
    try:
        trainer_module = import_module("dbreaker.ml.trainer")
        trajectory_module = import_module("dbreaker.ml.trajectory")
        Trajectory = trajectory_module.SelfPlayTrajectory

        def _on_game(game_index: int, trajectory: Trajectory) -> None:
            if not verbose:
                return
            n = len(trajectory.steps)
            rewards = trajectory.rewards
            mr = sum(rewards) / len(rewards) if rewards else 0.0
            typer.echo(
                f"game {game_index + 1}/{games} learner_steps={n} "
                f"ended_by={trajectory.ended_by} mean_reward={mr:.4f}"
            )

        config = trainer_module.PPOConfig(
            games=games,
            player_count=players,
            max_turns=max_turns,
            max_self_play_steps=max_self_play_steps,
            update_epochs=update_epochs,
            gamma=gamma,
            opponent_mix_prob=opponent_mix,
            opponent_strategies=_parse_comma_strs(opponents),
            champion_checkpoint=champion,
        )
        stats = trainer_module.train_self_play(
            config,
            checkpoint_out=checkpoint_out,
            seed=seed,
            from_checkpoint=from_checkpoint,
            game_seed_offset=game_seed_offset,
            on_game_complete=_on_game if verbose else None,
            metrics_out=metrics_out,
        )
    except ImportError as exc:
        typer.secho(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc
    entropy = (
        f" mean_entropy={stats.mean_entropy:.4f}"
        if getattr(stats, "mean_entropy", None) is not None
        else ""
    )
    typer.echo(
        f"trained games={stats.games} steps={stats.steps} "
        f"mean_reward={stats.mean_reward:.3f}{entropy} checkpoint={checkpoint_out}"
    )


@app.command("rl-search")
def rl_search(
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Directory for per-count runs and manifests."),
    ] = Path("checkpoints/rl-search"),
    players: str = typer.Option(
        "2,3,4,5",
        "--players",
        help="Comma-separated player counts (2-5).",
    ),
    runs: int = typer.Option(1, "--runs", min=1, help="Training runs per player count."),
    games_per_run: int = typer.Option(10, "--games-per-run", min=1),
    seed: int = typer.Option(1, help="Base seed; per-run seeds are derived."),
    max_turns: int = typer.Option(200, "--max-turns", min=1),
    max_self_play_steps: int = typer.Option(30_000, "--max-self-play-steps", min=1),
    update_epochs: int = typer.Option(2, "--update-epochs", min=1),
    gamma: float = typer.Option(0.99, "--gamma", min=0.0, max=1.0),
    opponent_mix: float = typer.Option(
        0.0,
        "--opponent-mix",
        min=0.0,
        max=1.0,
    ),
    opponents: str = typer.Option(
        "basic,aggressive,defensive,set_completion",
        "--opponents",
    ),
    champion: Annotated[
        Path | None,
        typer.Option("--champion", help="Optional champion checkpoint for opponent mixing."),
    ] = None,
) -> None:
    """Train count-specific checkpoints under output_dir with manifests (RL search loop)."""
    try:
        import_module("dbreaker.ml.trainer")
    except ImportError as exc:
        typer.secho(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc
    manifests = run_rl_search(
        RLSearchConfig(
            output_dir=output_dir,
            player_counts=_parse_comma_ints(players),
            runs_per_count=runs,
            games_per_run=games_per_run,
            seed=seed,
            max_turns=max_turns,
            max_self_play_steps=max_self_play_steps,
            update_epochs=update_epochs,
            gamma=gamma,
            opponent_mix_prob=opponent_mix,
            opponent_strategies=_parse_comma_strs(opponents),
            champion_checkpoint=champion,
        )
    )
    for manifest in manifests:
        typer.echo(
            f"{manifest.player_count}p run {manifest.run_index}: "
            f"checkpoint={manifest.checkpoint_path} manifest={manifest.manifest_path}"
        )


@app.command("rl-evaluate")
def rl_evaluate(
    candidate: str = typer.Option(
        ...,
        "--candidate",
        help="Candidate strategy, e.g. neural:path.pt",
    ),
    players: int = typer.Option(4, "--players", min=2, max=5),
    games: int = typer.Option(20, "--eval-games", min=1),
    seed: int = typer.Option(1),
    max_turns: int = typer.Option(200, "--max-turns", min=1),
    max_self_play_steps: int = typer.Option(30_000, "--max-self-play-steps", min=1),
    baselines: str = typer.Option(
        "basic,aggressive,defensive,set_completion",
        "--baselines",
    ),
    champions: Annotated[
        Path | None,
        typer.Option("--champions", help="champions.json for previous-best comparison."),
    ] = None,
    promote: bool = typer.Option(
        False,
        "--promote",
        help="If set, update champions.json when promotion guardrails pass.",
    ),
    checkpoint_path: Annotated[
        str | None,
        typer.Option(
            "--checkpoint-path",
            help="Path written to champions.json when promoting (default: strip neural: prefix).",
        ),
    ] = None,
    max_aborted_rate: float = typer.Option(
        0.0,
        "--max-aborted-rate",
        min=0.0,
        max=1.0,
    ),
) -> None:
    """Evaluate a candidate vs baselines (and optional champion) using tournament reporting."""
    result = evaluate_candidate(
        EvaluationConfig(
            player_count=players,
            candidate=candidate,
            baselines=_parse_comma_strs(baselines),
            champions_path=champions,
            games=games,
            seed=seed,
            max_turns=max_turns,
            max_self_play_steps=max_self_play_steps,
        )
    )
    typer.echo(result.report.to_markdown())
    if promote and champions is not None:
        decision = promote_champion(
            champions,
            result,
            checkpoint_path=_promotion_checkpoint(candidate, checkpoint_path),
            metadata={"cli": "rl-evaluate"},
            max_aborted_rate=max_aborted_rate,
        )
        typer.echo(f"promote: {decision.promoted} ({decision.reason})")
    elif promote:
        typer.secho("Error: --promote requires --champions", err=True)
        raise typer.Exit(2)


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


@app.command("benchmark-neural")
def benchmark_neural(
    games: int = typer.Option(2, min=0, help="Number of self-play games per training pass."),
    players: int = typer.Option(4, "--players", min=2, max=5, help="Players per table."),
    seed: int = typer.Option(1, help="Base seed; game n uses seed + n − 1."),
    max_turns: int = typer.Option(200, "--max-turns", min=1),
    max_self_play_steps: int = typer.Option(
        30_000,
        "--max-self-play-steps",
        min=1,
    ),
    update_epochs: int = typer.Option(2, "--update-epochs", min=1),
    learning_rate: float = typer.Option(3e-4, "--learning-rate"),
    gamma: float = typer.Option(0.99, "--gamma"),
    torch_seed: int | None = typer.Option(
        None,
        "--torch-seed",
        help="If set, torch.manual_seed before training (reproducible benchmarks).",
    ),
    output: str = typer.Option(
        "text",
        "--output",
        help="'text' for one key=value per line, 'json' for a single JSON object.",
    ),
) -> None:
    """Measure neural PPO self-play training throughput (steps/sec) and phase timings."""
    try:
        report = run_neural_training_benchmark(
            games=games,
            player_count=players,
            seed=seed,
            max_turns=max_turns,
            max_self_play_steps=max_self_play_steps,
            update_epochs=update_epochs,
            learning_rate=learning_rate,
            gamma=gamma,
            torch_seed=torch_seed,
        )
    except ImportError as exc:
        typer.secho(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc
    out = output.lower().strip()
    if out not in {"text", "json"}:
        typer.secho(
            f"Error: --output must be 'text' or 'json', got {output!r}.",
            err=True,
        )
        raise typer.Exit(2)
    if out == "json":
        typer.echo(report.to_json())
    else:
        for line in report.to_text_lines():
            typer.echo(line)


_DEFAULT_WEB_DATA = Path(".dbreaker")
_DEFAULT_API_HOST = "127.0.0.1"
_DEFAULT_API_PORT = 8765
_DEFAULT_FRONTEND_HOST = "127.0.0.1"
_DEFAULT_FRONTEND_PORT = 5173


def _web_dir() -> Path:
    repo_web = Path(__file__).resolve().parents[3] / "web"
    if repo_web.is_dir():
        return repo_web
    cwd_web = Path.cwd() / "web"
    if cwd_web.is_dir():
        return cwd_web
    typer.secho(
        "Error: could not find the Vite web/ directory. Run from the repository root "
        "or use `dbreaker api` for the backend only.",
        err=True,
    )
    raise typer.Exit(2)


def _run_api_server(
    *,
    host: str,
    port: int,
    data_dir: Path | None,
    artifacts_dir: Path | None,
) -> None:
    try:
        uvicorn = import_module("uvicorn")
    except ImportError as exc:
        typer.secho(
            "Error: uvicorn is required. Install the web or dev extra "
            "(e.g. `uv sync --all-extras`).",
            err=True,
        )
        raise typer.Exit(2) from exc
    web_module = import_module("dbreaker.web")

    root = data_dir if data_dir is not None else _DEFAULT_WEB_DATA
    artifact_root = artifacts_dir if artifacts_dir is not None else root / "artifacts"
    api_app = web_module.create_app(data_root=root, artifact_root=artifact_root)
    uvicorn.run(api_app, host=host, port=port, log_level="info")


def _path_option(name: str, value: Path | None) -> list[str]:
    if value is None:
        return []
    return [name, str(value)]


def _terminate_process(proc: subprocess.Popen[object]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _run_full_web_stack(
    *,
    host: str,
    port: int,
    frontend_host: str,
    frontend_port: int,
    data_dir: Path | None,
    artifacts_dir: Path | None,
    open_browser: bool,
) -> None:
    frontend_url = f"http://{frontend_host}:{frontend_port}/"
    api_url = f"http://{host}:{port}/"
    backend_cmd = [
        sys.executable,
        "-m",
        "dbreaker.cli.app",
        "api",
        "--host",
        host,
        "--port",
        str(port),
        *_path_option("--data-dir", data_dir),
        *_path_option("--artifacts-dir", artifacts_dir),
    ]
    frontend_cmd = [
        "npm",
        "run",
        "dev",
        "--",
        "--host",
        frontend_host,
        "--port",
        str(frontend_port),
    ]

    typer.echo(f"Frontend: {frontend_url}")
    typer.echo(f"API: {api_url}")
    backend_proc = subprocess.Popen(backend_cmd)
    try:
        frontend_proc = subprocess.Popen(frontend_cmd, cwd=_web_dir())
    except FileNotFoundError as exc:
        _terminate_process(backend_proc)
        typer.secho(
            "Error: npm was not found. Install Node.js/npm or use `dbreaker api` "
            "for the backend only.",
            err=True,
        )
        raise typer.Exit(2) from exc
    procs = [backend_proc, frontend_proc]
    try:
        if open_browser:
            time.sleep(1)
            webbrowser.open(frontend_url)
        while True:
            for proc in procs:
                code = proc.poll()
                if code is not None:
                    raise typer.Exit(code)
            time.sleep(0.25)
    except KeyboardInterrupt:
        typer.echo("Shutting down web stack...")
    finally:
        for proc in reversed(procs):
            _terminate_process(proc)


@app.command("api")
def api(
    host: str = typer.Option(_DEFAULT_API_HOST, help="Bind address for the API server."),
    port: int = typer.Option(_DEFAULT_API_PORT, help="Port for the API server."),
    data_dir: Annotated[
        Path | None,
        typer.Option(help="Data root (SQLite and default layout)."),
    ] = None,
    artifacts_dir: Annotated[
        Path | None,
        typer.Option(
            help="Artifact root; defaults to <data_dir>/artifacts if omitted.",
        ),
    ] = None,
) -> None:
    """Run only the FastAPI backend service."""
    _run_api_server(
        host=host,
        port=port,
        data_dir=data_dir,
        artifacts_dir=artifacts_dir,
    )


@app.command("web")
def web(
    host: str = typer.Option(_DEFAULT_API_HOST, help="Bind address for the API server."),
    port: int = typer.Option(_DEFAULT_API_PORT, help="Port for the API server."),
    frontend_host: str = typer.Option(
        _DEFAULT_FRONTEND_HOST,
        "--frontend-host",
        help="Bind address for the Vite frontend.",
    ),
    frontend_port: int = typer.Option(
        _DEFAULT_FRONTEND_PORT,
        "--frontend-port",
        help="Port for the Vite frontend.",
    ),
    open_browser: bool = typer.Option(
        True,
        "--open/--no-open",
        help="Open the frontend URL in a browser after starting.",
    ),
    data_dir: Annotated[
        Path | None,
        typer.Option(help="Data root (SQLite and default layout)."),
    ] = None,
    artifacts_dir: Annotated[
        Path | None,
        typer.Option(
            help="Artifact root; defaults to <data_dir>/artifacts if omitted.",
        ),
    ] = None,
) -> None:
    """Run the full local web app: FastAPI backend plus Vite frontend."""
    _run_full_web_stack(
        host=host,
        port=port,
        frontend_host=frontend_host,
        frontend_port=frontend_port,
        data_dir=data_dir,
        artifacts_dir=artifacts_dir,
        open_browser=open_browser,
    )


@app.command()
def replay(path: Path) -> None:
    """Print events from a JSONL replay file."""
    for event in read_events(path):
        typer.echo(f"{event.turn}: {event.type} {event.reason_summary}")


if __name__ == "__main__":
    app()

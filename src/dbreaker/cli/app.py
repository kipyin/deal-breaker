from __future__ import annotations

import subprocess
import sys
import time
import webbrowser
from importlib import import_module
from pathlib import Path
from typing import Annotated, Literal

import typer
from loguru import logger

from dbreaker.cli.play import run_interactive_play, run_scripted_play
from dbreaker.experiments.benchmark import run_benchmark, run_neural_training_benchmark
from dbreaker.experiments.rl_search import (
    EvaluationConfig,
    RLSearchConfig,
    evaluate_candidate,
    promote_champion,
    run_rl_search,
)
from dbreaker.experiments.strategy_summary_report import (
    checkpoint_payload_dict,
    load_metrics_json,
    render_strategy_summary_text,
)
from dbreaker.experiments.tournament import GameProgress, run_tournament
from dbreaker.replay.log_store import read_events

app = typer.Typer(help="Monopoly Deal AI strategy research platform.")


def _configure_logging(verbose: bool) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        level=level,
        format="<level>{level}</level> | {message}",
        colorize=False,
    )
    if verbose:
        logger.debug("CLI debug logging enabled")


@app.callback()
def _main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help=(
            "Enable debug logging on stderr. "
            "Use before the subcommand (e.g. dbreaker -v benchmark). "
            "Per-command progress still uses that command's own --verbose."
        ),
    ),
) -> None:
    """Monopoly Deal AI strategy research platform."""
    _configure_logging(verbose)


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
    logger.info(
        "play players={} ai_strategy={} output={} seed={}",
        players,
        ai_strategy,
        mode,
        seed,
    )
    if commands is None:
        logger.info("play mode=interactive")
        run_interactive_play(players=players, ai_strategy=ai_strategy)
        return
    path = str(commands)
    logger.info("play mode=scripted commands={}", path)
    logger.debug(
        "play scripted detail command_source={} seed={}",
        "stdin" if path == "-" else path,
        seed,
    )
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
        help="Per-game progress via logging (stderr): -v compact, -vv seed and full rank order.",
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
    """Run an AI self-play tournament.

    Baseline reporting uses ``dbreaker.experiments.eval_protocol.EVAL_PROTOCOL_REVISION``;
    see module docstring for surfaced metrics (win rate, Elo, avg rank, outcome shares).
    """
    logger.info(
        "tournament games={} players={} seed={} max_turns={} max_self_play_steps={} "
        "stalemate_turns={} progress_verbose_lines={}",
        games,
        players,
        seed,
        max_turns,
        max_self_play_steps,
        stalemate_turns,
        verbose,
    )
    logger.debug("tournament strategies={!r}", strategies)
    need_lines = bool(log_path) or verbose >= 1
    line_detail = min(verbose, 2) >= 2

    def on_game(p: GameProgress) -> None:
        line = _format_tournament_game_line(p, detail=line_detail)
        if log_path is not None:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        if verbose >= 1:
            logger.info("{}", line)

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
    rollout_batch_games: int = typer.Option(
        500,
        "--rollout-batch-games",
        min=1,
        help=(
            "Collect at most this many self-play games before each PPO update. "
            "Smaller values reduce peak RAM; large --games runs split into multiple updates."
        ),
    ),
    rollout_target_steps: Annotated[
        int | None,
        typer.Option(
            "--rollout-target-steps",
            min=1,
            help=(
                "If set, trigger PPO updates after collecting at least this many learner "
                "steps instead of using only --rollout-batch-games."
            ),
        ),
    ] = None,
    min_rollout_games: int = typer.Option(
        1,
        "--min-rollout-games",
        min=1,
        help="Minimum games to collect before honoring --rollout-target-steps.",
    ),
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
    fast_single_learner: bool = typer.Option(
        False,
        "--fast-single-learner",
        help=(
            "Aggressive fast-training mode: one neural learner seat per game; "
            "other seats use configured opponents."
        ),
    ),
    rollout_max_steps_per_game: Annotated[
        int | None,
        typer.Option(
            "--rollout-max-steps-per-game",
            min=1,
            help="Optional per-game rollout step cap; truncated games use ranking-shaped rewards.",
        ),
    ] = None,
    max_policy_actions: Annotated[
        int | None,
        typer.Option(
            "--max-policy-actions",
            min=1,
            help="Optional legal-action candidate cap before neural scoring.",
        ),
    ] = None,
    rollout_workers: int = typer.Option(
        1,
        "--rollout-workers",
        min=1,
        help=(
            "Parallel CPU rollout workers per batch. Incompatible with --rollout-target-steps. "
            "Main process stays single-threaded for PPO; worker order vs strict serial RNG may differ."
        ),
    ),
    policy_top_k: int = typer.Option(
        3,
        "--policy-top-k",
        min=0,
        help="Per-step softmax top-k telemetry (0 disables extra logits work).",
    ),
    telemetry_jsonl: Annotated[
        Path | None,
        typer.Option(
            "--telemetry-jsonl",
            help="Append one JSON object per learner step (requires rollout_workers=1).",
        ),
    ] = None,
    structured_policy: bool = typer.Option(
        False,
        "--structured-policy",
        help="Initialize StructuredPolicyValueNetwork instead of the default MLP policy.",
    ),
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
        help="Log one line per self-play game (steps, outcome, mean reward) to stderr.",
    ),
    metrics_out: Annotated[
        Path | None,
        typer.Option(
            "--metrics-out",
            help="Write extended training metrics and per-game rows as JSON.",
        ),
    ] = None,
    device: str = typer.Option(
        "auto",
        "--device",
        help="PyTorch device: auto (MPS on Apple Silicon, else CUDA if available, else CPU), cpu, mps, cuda.",
    ),
) -> None:
    """Train a checkpoint-backed neural policy with small PPO-style self-play updates.

    Parallel rollouts (--rollout-workers > 1) skip JSONL telemetry and cannot combine with
    --rollout-target-steps (step-budget batches are serial-only).
    """
    logger.info(
        "train games={} players={} checkpoint_out={} seed={} game_seed_offset={} "
        "max_turns={} max_self_play_steps={} rollout_batch_games={} update_epochs={} gamma={} opponent_mix={} "
        "rollout_target_steps={} fast_single_learner={} rollout_max_steps_per_game={} "
        "max_policy_actions={} verbose={} metrics_out={}",
        games,
        players,
        checkpoint_out,
        seed,
        game_seed_offset,
        max_turns,
        max_self_play_steps,
        rollout_batch_games,
        update_epochs,
        gamma,
        opponent_mix,
        rollout_target_steps,
        fast_single_learner,
        rollout_max_steps_per_game,
        max_policy_actions,
        verbose,
        metrics_out,
    )
    logger.debug(
        "train opponents={!r} champion={} from_checkpoint={}",
        opponents,
        champion,
        from_checkpoint,
    )
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
            logger.info(
                "game {}/{} learner_steps={} ended_by={} mean_reward={:.4f}",
                game_index + 1,
                games,
                n,
                trajectory.ended_by,
                mr,
            )

        pk = None if policy_top_k == 0 else policy_top_k
        config = trainer_module.PPOConfig(
            games=games,
            rollout_batch_games=rollout_batch_games,
            rollout_target_steps=rollout_target_steps,
            min_rollout_games=min_rollout_games,
            player_count=players,
            max_turns=max_turns,
            max_self_play_steps=max_self_play_steps,
            update_epochs=update_epochs,
            gamma=gamma,
            opponent_mix_prob=opponent_mix,
            opponent_strategies=_parse_comma_strs(opponents),
            champion_checkpoint=champion,
            fast_single_learner=fast_single_learner,
            rollout_max_steps_per_game=rollout_max_steps_per_game,
            max_policy_actions=max_policy_actions,
            policy_top_k=pk,
            rollout_workers=rollout_workers,
        )
        stats = trainer_module.train_self_play(
            config,
            checkpoint_out=checkpoint_out,
            seed=seed,
            from_checkpoint=from_checkpoint,
            structured_policy=structured_policy,
            game_seed_offset=game_seed_offset,
            on_game_complete=_on_game if verbose else None,
            metrics_out=metrics_out,
            telemetry_jsonl=telemetry_jsonl,
            device=device,
        )
    except ImportError as exc:
        typer.secho(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc
    entropy = (
        f" mean_entropy={stats.mean_entropy:.4f}"
        if getattr(stats, "mean_entropy", None) is not None
        else ""
    )
    dev = getattr(stats, "training_device", None) or "?"
    typer.echo(
        f"trained games={stats.games} steps={stats.steps} "
        f"mean_reward={stats.mean_reward:.3f}{entropy} "
        f"device={dev} checkpoint={checkpoint_out}"
    )


@app.command("strategy-summary")
def strategy_summary(
    metrics: Annotated[
        Path | None,
        typer.Option("--metrics", help="Training metrics JSON (from TrainingStats.as_dict())."),
    ] = None,
    checkpoint: Annotated[
        Path | None,
        typer.Option("--checkpoint", help="Neural checkpoint .pt for manifest snippet."),
    ] = None,
    telemetry: Annotated[
        Path | None,
        typer.Option("--telemetry", help="Trajectory telemetry JSONL from train --telemetry-jsonl."),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", "-o", help="Also write the report to this file."),
    ] = None,
) -> None:
    """Summarize training metrics, optional checkpoint manifest, and telemetry histograms."""
    if metrics is None and checkpoint is None and telemetry is None:
        typer.secho(
            "Error: provide at least one of --metrics, --checkpoint, --telemetry.",
            err=True,
        )
        raise typer.Exit(2)
    metrics_payload = load_metrics_json(metrics) if metrics is not None else None
    ck_payload = checkpoint_payload_dict(checkpoint) if checkpoint is not None else None
    text = render_strategy_summary_text(
        metrics=metrics_payload,
        checkpoint_payload=ck_payload,
        telemetry_path=telemetry,
    )
    typer.echo(text, nl=False)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")


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
    rollout_batch_games: int = typer.Option(
        500,
        "--rollout-batch-games",
        min=1,
        help=(
            "Collect at most this many self-play games per PPO update (same semantics as "
            "`dbreaker train --rollout-batch-games`)."
        ),
    ),
    rollout_target_steps: Annotated[
        int | None,
        typer.Option("--rollout-target-steps", min=1),
    ] = None,
    min_rollout_games: int = typer.Option(1, "--min-rollout-games", min=1),
    opponents: str = typer.Option(
        "basic,aggressive,defensive,set_completion",
        "--opponents",
    ),
    champion: Annotated[
        Path | None,
        typer.Option("--champion", help="Optional champion checkpoint for opponent mixing."),
    ] = None,
    fast_single_learner: bool = typer.Option(False, "--fast-single-learner"),
    rollout_max_steps_per_game: Annotated[
        int | None,
        typer.Option("--rollout-max-steps-per-game", min=1),
    ] = None,
    max_policy_actions: Annotated[
        int | None,
        typer.Option("--max-policy-actions", min=1),
    ] = None,
    rollout_workers: int = typer.Option(
        1,
        "--rollout-workers",
        min=1,
        help=(
            "Parallel CPU rollout workers per batch (cannot combine with --rollout-target-steps)."
        ),
    ),
    policy_top_k: int = typer.Option(
        3,
        "--policy-top-k",
        min=0,
        help="Per-step softmax top-k telemetry (0 disables extra logits scoring).",
    ),
    telemetry_per_run: bool = typer.Option(
        False,
        "--telemetry-per-run",
        help=(
            "Write run-NNN.telemetry.jsonl beside each checkpoint (serial rollouts only; "
            "same constraints as train --telemetry-jsonl)."
        ),
    ),
    structured_policy: bool = typer.Option(
        False,
        "--structured-policy",
        help="Use StructuredPolicyValueNetwork instead of the default MLP policy.",
    ),
) -> None:
    """Train count-specific checkpoints under output_dir with manifests (RL search loop)."""
    logger.info(
        "rl-search output_dir={} runs={} games_per_run={} seed={} max_turns={} "
        "max_self_play_steps={} rollout_batch_games={} update_epochs={} gamma={} opponent_mix={}",
        output_dir,
        runs,
        games_per_run,
        seed,
        max_turns,
        max_self_play_steps,
        rollout_batch_games,
        update_epochs,
        gamma,
        opponent_mix,
    )
    logger.debug(
        "rl-search players={!r} opponents={!r} champion={}",
        players,
        opponents,
        champion,
    )
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
            rollout_batch_games=rollout_batch_games,
            rollout_target_steps=rollout_target_steps,
            min_rollout_games=min_rollout_games,
            seed=seed,
            max_turns=max_turns,
            max_self_play_steps=max_self_play_steps,
            update_epochs=update_epochs,
            gamma=gamma,
            opponent_mix_prob=opponent_mix,
            opponent_strategies=_parse_comma_strs(opponents),
            champion_checkpoint=champion,
            fast_single_learner=fast_single_learner,
            rollout_max_steps_per_game=rollout_max_steps_per_game,
            max_policy_actions=max_policy_actions,
            rollout_workers=rollout_workers,
            policy_top_k=None if policy_top_k == 0 else policy_top_k,
            telemetry_per_run=telemetry_per_run,
            structured_policy=structured_policy,
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
    logger.info(
        "rl-evaluate candidate={} players={} games={} seed={} promote={} champions={}",
        candidate,
        players,
        games,
        seed,
        promote,
        champions,
    )
    logger.debug("rl-evaluate baselines={!r} max_aborted_rate={}", baselines, max_aborted_rate)
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
    logger.info(
        "evaluate candidate={} baseline={} games={} players={} seed={} max_turns={} "
        "max_self_play_steps={}",
        candidate,
        baseline,
        games,
        players,
        seed,
        max_turns,
        max_self_play_steps,
    )
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
    logger.info(
        "benchmark games={} players={} seed={} max_turns={} max_self_play_steps={} "
        "stalemate_turns={} output={}",
        games,
        players,
        seed,
        max_turns,
        max_self_play_steps,
        stalemate_turns,
        out,
    )
    logger.debug("benchmark strategies={}", names)
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
    rollout_target_steps: Annotated[
        int | None,
        typer.Option("--rollout-target-steps", min=1),
    ] = None,
    min_rollout_games: int = typer.Option(1, "--min-rollout-games", min=1),
    fast_single_learner: bool = typer.Option(False, "--fast-single-learner"),
    rollout_max_steps_per_game: Annotated[
        int | None,
        typer.Option("--rollout-max-steps-per-game", min=1),
    ] = None,
    max_policy_actions: Annotated[
        int | None,
        typer.Option("--max-policy-actions", min=1),
    ] = None,
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
    logger.info(
        "benchmark-neural games={} players={} seed={} max_turns={} max_self_play_steps={} "
        "update_epochs={} learning_rate={} gamma={} rollout_target_steps={} "
        "fast_single_learner={} rollout_max_steps_per_game={} max_policy_actions={} "
        "torch_seed={} output={}",
        games,
        players,
        seed,
        max_turns,
        max_self_play_steps,
        update_epochs,
        learning_rate,
        gamma,
        rollout_target_steps,
        fast_single_learner,
        rollout_max_steps_per_game,
        max_policy_actions,
        torch_seed,
        output.lower().strip(),
    )
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
            rollout_target_steps=rollout_target_steps,
            min_rollout_games=min_rollout_games,
            fast_single_learner=fast_single_learner,
            rollout_max_steps_per_game=rollout_max_steps_per_game,
            max_policy_actions=max_policy_actions,
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
    logger.info(
        "api starting host={} port={} data_root={} artifact_root={}",
        host,
        port,
        root,
        artifact_root,
    )
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
    logger.info(
        (
            "web stack starting frontend_url={} api_url={} open_browser={} "
            "data_dir={} artifacts_dir={}"
        ),
        frontend_url,
        api_url,
        open_browser,
        data_dir,
        artifacts_dir,
    )
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
        logger.info("web stack interrupted by user")
        typer.echo("Shutting down web stack...")
    finally:
        logger.info("web stack shutting down processes")
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
    logger.info("replay path={}", path.resolve())
    for event in read_events(path):
        typer.echo(f"{event.turn}: {event.type} {event.reason_summary}")


if __name__ == "__main__":
    app()

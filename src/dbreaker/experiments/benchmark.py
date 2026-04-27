from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

from dbreaker.experiments.runner import GameResult, run_self_play_game
from dbreaker.ml.trainer import PPOConfig, SelfPlayPhaseTimings, train_self_play
from dbreaker.strategies.registry import create_strategy


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    total_games: int
    total_engine_steps: int
    elapsed_seconds: float
    games_per_sec: float
    steps_per_sec: float
    games_winner: int
    games_max_turn: int
    games_stalemate: int
    games_aborted: int
    total_turns: int
    average_turns_per_game: float
    average_steps_per_game: float
    base_seed: int
    player_count: int
    strategy_names: tuple[str, ...]
    max_turns: int
    max_self_play_steps: int
    stalemate_turns: int | None

    def to_text_lines(self) -> list[str]:
        return [
            f"total_games={self.total_games}",
            f"total_engine_steps={self.total_engine_steps}",
            f"elapsed_seconds={self.elapsed_seconds:.6f}",
            f"games_per_sec={self.games_per_sec:.6f}",
            f"steps_per_sec={self.steps_per_sec:.6f}",
            f"games_winner={self.games_winner}",
            f"games_max_turn={self.games_max_turn}",
            f"games_stalemate={self.games_stalemate}",
            f"games_aborted={self.games_aborted}",
            f"average_turns_per_game={self.average_turns_per_game:.6f}",
            f"average_steps_per_game={self.average_steps_per_game:.6f}",
            f"base_seed={self.base_seed}",
            f"player_count={self.player_count}",
            f"strategies={','.join(self.strategy_names)}",
            f"max_turns={self.max_turns}",
            f"max_self_play_steps={self.max_self_play_steps}",
            f"stalemate_turns={self.stalemate_turns}",
        ]

    def to_json(self) -> str:
        payload = asdict(self)
        payload["strategy_names"] = list(self.strategy_names)
        return json.dumps(payload, sort_keys=True)


def _aggregate_results(
    results: list[GameResult],
    *,
    elapsed: float,
    base_seed: int,
    player_count: int,
    strategy_names: tuple[str, ...],
    max_turns: int,
    max_self_play_steps: int,
    stalemate_turns: int | None,
) -> BenchmarkReport:
    n = len(results)
    total_engine_steps = sum(r.self_play_steps for r in results)
    total_turns = sum(r.turns for r in results)
    games_winner = sum(1 for r in results if r.ended_by == "winner")
    games_max_turn = sum(1 for r in results if r.ended_by == "max_turns")
    games_stalemate = sum(1 for r in results if r.ended_by == "stalemate")
    games_aborted = sum(1 for r in results if r.ended_by == "aborted")
    safe_elapsed = elapsed if elapsed > 0.0 else 0.0
    games_per_sec = (n / safe_elapsed) if safe_elapsed > 0.0 else 0.0
    steps_per_sec = (total_engine_steps / safe_elapsed) if safe_elapsed > 0.0 else 0.0
    avg_turns = (total_turns / n) if n else 0.0
    avg_steps = (total_engine_steps / n) if n else 0.0
    return BenchmarkReport(
        total_games=n,
        total_engine_steps=total_engine_steps,
        elapsed_seconds=elapsed,
        games_per_sec=games_per_sec,
        steps_per_sec=steps_per_sec,
        games_winner=games_winner,
        games_max_turn=games_max_turn,
        games_stalemate=games_stalemate,
        games_aborted=games_aborted,
        total_turns=total_turns,
        average_turns_per_game=avg_turns,
        average_steps_per_game=avg_steps,
        base_seed=base_seed,
        player_count=player_count,
        strategy_names=strategy_names,
        max_turns=max_turns,
        max_self_play_steps=max_self_play_steps,
        stalemate_turns=stalemate_turns,
    )


def run_benchmark(
    *,
    games: int,
    player_count: int,
    strategy_names: list[str],
    seed: int = 1,
    max_turns: int = 200,
    max_self_play_steps: int = 30_000,
    stalemate_turns: int | None = 25,
) -> BenchmarkReport:
    """Run deterministic self-play games and return throughput and outcome stats.

    Game *i* uses ``seed=seed + i`` (0-based *i*), matching
    :func:`dbreaker.experiments.tournament.run_tournament`.
    Strategy seat assignment for each game matches tournament rotation of the given strategy list.
    """
    if games < 0:
        raise ValueError("games must be non-negative")
    if player_count < 2:
        raise ValueError("player_count must be at least 2")
    if not strategy_names:
        raise ValueError("at least one strategy name is required")
    base_strategies = [create_strategy(name) for name in strategy_names]
    t0 = time.perf_counter()
    results: list[GameResult] = []
    for index in range(games):
        rotated = [
            base_strategies[(index + offset) % len(base_strategies)]
            for offset in range(player_count)
        ]
        result = run_self_play_game(
            game_id=f"bench-{index + 1}",
            player_count=player_count,
            strategies=rotated,
            seed=seed + index,
            max_turns=max_turns,
            max_self_play_steps=max_self_play_steps,
            stalemate_turns=stalemate_turns,
        )
        results.append(result)
    elapsed = time.perf_counter() - t0
    return _aggregate_results(
        results,
        elapsed=elapsed,
        base_seed=seed,
        player_count=player_count,
        strategy_names=tuple(strategy_names),
        max_turns=max_turns,
        max_self_play_steps=max_self_play_steps,
        stalemate_turns=stalemate_turns,
    )


@dataclass(frozen=True, slots=True)
class NeuralTrainingBenchmarkReport:
    """Throughput and phase timings for one :func:`train_self_play` call."""

    games: int
    player_count: int
    training_steps: int
    elapsed_seconds: float
    rollout_seconds: float
    ppo_update_seconds: float
    training_steps_per_sec: float
    games_per_sec: float
    mean_reward: float
    mean_entropy: float | None
    mean_legal_actions_per_step: float
    max_turns: int
    max_self_play_steps: int
    update_epochs: int
    learning_rate: float
    gamma: float
    seed: int | None
    torch_seed: int | None

    def to_text_lines(self) -> list[str]:
        ent = "null" if self.mean_entropy is None else f"{self.mean_entropy:.6f}"
        return [
            f"games={self.games}",
            f"player_count={self.player_count}",
            f"training_steps={self.training_steps}",
            f"elapsed_seconds={self.elapsed_seconds:.6f}",
            f"rollout_seconds={self.rollout_seconds:.6f}",
            f"ppo_update_seconds={self.ppo_update_seconds:.6f}",
            f"training_steps_per_sec={self.training_steps_per_sec:.6f}",
            f"games_per_sec={self.games_per_sec:.6f}",
            f"mean_reward={self.mean_reward:.6f}",
            f"mean_entropy={ent}",
            f"mean_legal_actions_per_step={self.mean_legal_actions_per_step:.6f}",
            f"max_turns={self.max_turns}",
            f"max_self_play_steps={self.max_self_play_steps}",
            f"update_epochs={self.update_epochs}",
            f"learning_rate={self.learning_rate}",
            f"gamma={self.gamma}",
            f"seed={self.seed}",
            f"torch_seed={self.torch_seed}",
        ]

    def to_json(self) -> str:
        payload = asdict(self)
        return json.dumps(payload, sort_keys=True)


def run_neural_training_benchmark(
    *,
    games: int,
    player_count: int = 4,
    seed: int | None = 1,
    max_turns: int = 200,
    max_self_play_steps: int = 30_000,
    learning_rate: float = 3e-4,
    clip_epsilon: float = 0.2,
    value_coef: float = 0.5,
    entropy_coef: float = 0.01,
    update_epochs: int = 2,
    gamma: float = 0.99,
    opponent_mix_prob: float = 0.0,
    torch_seed: int | None = None,
) -> NeuralTrainingBenchmarkReport:
    """Run a single PPO self-play training pass and report wall time and throughput.

    Deterministic when ``seed`` is fixed (game *i* uses ``seed + i``).
    Requires the ``ml`` extra (PyTorch).
    """
    if games < 0:
        raise ValueError("games must be non-negative")
    if player_count < 2:
        raise ValueError("player_count must be at least 2")
    config = PPOConfig(
        games=games,
        player_count=player_count,
        max_turns=max_turns,
        max_self_play_steps=max_self_play_steps,
        learning_rate=learning_rate,
        clip_epsilon=clip_epsilon,
        value_coef=value_coef,
        entropy_coef=entropy_coef,
        update_epochs=update_epochs,
        gamma=gamma,
        opponent_mix_prob=opponent_mix_prob,
    )
    timings = SelfPlayPhaseTimings()
    stats = train_self_play(
        config, seed=seed, phase_timings=timings, torch_seed=torch_seed
    )
    elapsed = timings.total_seconds
    safe_elapsed = elapsed if elapsed > 0.0 else 0.0
    steps = stats.steps
    training_steps_per_sec = (steps / safe_elapsed) if safe_elapsed > 0.0 else 0.0
    games_per_sec = (games / safe_elapsed) if safe_elapsed > 0.0 else 0.0
    return NeuralTrainingBenchmarkReport(
        games=games,
        player_count=player_count,
        training_steps=steps,
        elapsed_seconds=elapsed,
        rollout_seconds=timings.rollout_seconds,
        ppo_update_seconds=timings.ppo_update_seconds,
        training_steps_per_sec=training_steps_per_sec,
        games_per_sec=games_per_sec,
        mean_reward=stats.mean_reward,
        mean_entropy=stats.mean_entropy,
        mean_legal_actions_per_step=timings.mean_legal_actions_per_step,
        max_turns=max_turns,
        max_self_play_steps=max_self_play_steps,
        update_epochs=update_epochs,
        learning_rate=learning_rate,
        gamma=gamma,
        seed=seed,
        torch_seed=torch_seed,
    )

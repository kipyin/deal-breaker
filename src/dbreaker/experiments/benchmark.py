from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

from dbreaker.experiments.runner import GameResult, run_self_play_game
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

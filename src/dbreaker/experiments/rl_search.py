from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from dbreaker.experiments.reports import TournamentReport
from dbreaker.experiments.tournament import run_tournament
from dbreaker.ml.features import FEATURE_SCHEMA_VERSION
from dbreaker.ml.trainer import PPOConfig, TrainingStats, train_self_play

VALID_PLAYER_COUNTS = (2, 3, 4, 5)
DEFAULT_BASELINES = ("basic", "aggressive", "defensive", "set_completion")


class TrainingFn(Protocol):
    def __call__(
        self,
        config: PPOConfig,
        *,
        checkpoint_out: Path | None = None,
        seed: int | None = None,
        structured_policy: bool = False,
        telemetry_jsonl: Path | None = None,
        **kwargs: Any,
    ) -> TrainingStats: ...


@dataclass(frozen=True, slots=True)
class RLSearchConfig:
    output_dir: Path
    player_counts: tuple[int, ...] = VALID_PLAYER_COUNTS
    runs_per_count: int = 1
    games_per_run: int = 10
    rollout_batch_games: int = 500
    rollout_target_steps: int | None = None
    min_rollout_games: int = 1
    seed: int = 1
    max_turns: int = 200
    max_self_play_steps: int = 30_000
    update_epochs: int = 2
    gamma: float = 0.99
    opponent_mix_prob: float = 0.0
    opponent_strategies: tuple[str, ...] = DEFAULT_BASELINES
    champion_checkpoint: Path | None = None
    fast_single_learner: bool = False
    rollout_max_steps_per_game: int | None = None
    max_policy_actions: int | None = None
    rollout_workers: int = 1
    policy_top_k: int | None = 3
    telemetry_per_run: bool = False
    structured_policy: bool = False


@dataclass(frozen=True, slots=True)
class RLRunManifest:
    player_count: int
    run_index: int
    seed: int
    checkpoint_path: str
    manifest_path: str
    games: int
    update_epochs: int
    max_turns: int
    max_self_play_steps: int
    feature_schema: str
    training: dict[str, int | float | str | None]

    def as_dict(self) -> dict[str, Any]:
        return {
            "player_count": self.player_count,
            "run_index": self.run_index,
            "seed": self.seed,
            "checkpoint_path": self.checkpoint_path,
            "manifest_path": self.manifest_path,
            "games": self.games,
            "update_epochs": self.update_epochs,
            "max_turns": self.max_turns,
            "max_self_play_steps": self.max_self_play_steps,
            "feature_schema": self.feature_schema,
            "training": self.training,
        }


@dataclass(frozen=True, slots=True)
class ChampionEntry:
    player_count: int
    checkpoint_path: str
    evaluation_score: float
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "player_count": self.player_count,
            "checkpoint_path": self.checkpoint_path,
            "evaluation_score": self.evaluation_score,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class EvaluationConfig:
    player_count: int
    candidate: str
    baselines: tuple[str, ...] = DEFAULT_BASELINES
    champions_path: Path | None = None
    games: int = 20
    seed: int = 1
    max_turns: int = 200
    max_self_play_steps: int = 30_000


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    player_count: int
    candidate: str
    baselines: tuple[str, ...]
    previous_champion: str | None
    report: TournamentReport
    candidate_score: float
    strategy_scores: dict[str, float]

    @property
    def total_games(self) -> int:
        return (
            self.report.games_with_winner
            + self.report.games_max_turn
            + self.report.games_stalemate
            + self.report.games_aborted
        )

    @property
    def aborted_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.report.games_aborted / self.total_games

    @property
    def stalemate_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.report.games_stalemate / self.total_games

    @property
    def max_turn_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.report.games_max_turn / self.total_games


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    promoted: bool
    reason: str


def run_rl_search(
    config: RLSearchConfig,
    *,
    train_fn: TrainingFn = train_self_play,
) -> list[RLRunManifest]:
    _validate_player_counts(config.player_counts)
    if config.runs_per_count < 1:
        raise ValueError("runs_per_count must be at least 1")
    if config.games_per_run < 1:
        raise ValueError("games_per_run must be at least 1")

    manifests: list[RLRunManifest] = []
    for player_count in config.player_counts:
        for run_index in range(1, config.runs_per_count + 1):
            run_dir = config.output_dir / f"{player_count}p"
            checkpoint_path = run_dir / f"run-{run_index:03d}.pt"
            manifest_path = run_dir / f"run-{run_index:03d}.json"
            run_seed = _run_seed(config.seed, player_count=player_count, run_index=run_index)
            ppo_config = PPOConfig(
                games=config.games_per_run,
                rollout_batch_games=config.rollout_batch_games,
                rollout_target_steps=config.rollout_target_steps,
                min_rollout_games=config.min_rollout_games,
                player_count=player_count,
                max_turns=config.max_turns,
                max_self_play_steps=config.max_self_play_steps,
                update_epochs=config.update_epochs,
                gamma=config.gamma,
                opponent_mix_prob=config.opponent_mix_prob,
                opponent_strategies=config.opponent_strategies,
                champion_checkpoint=config.champion_checkpoint,
                fast_single_learner=config.fast_single_learner,
                rollout_max_steps_per_game=config.rollout_max_steps_per_game,
                max_policy_actions=config.max_policy_actions,
                policy_top_k=config.policy_top_k,
                rollout_workers=config.rollout_workers,
            )
            telemetry_jsonl: Path | None = None
            if config.telemetry_per_run:
                telemetry_jsonl = run_dir / f"run-{run_index:03d}.telemetry.jsonl"
            stats = train_fn(
                ppo_config,
                checkpoint_out=checkpoint_path,
                seed=run_seed,
                structured_policy=config.structured_policy,
                telemetry_jsonl=telemetry_jsonl,
            )
            manifest = RLRunManifest(
                player_count=player_count,
                run_index=run_index,
                seed=run_seed,
                checkpoint_path=str(checkpoint_path),
                manifest_path=str(manifest_path),
                games=config.games_per_run,
                update_epochs=config.update_epochs,
                max_turns=config.max_turns,
                max_self_play_steps=config.max_self_play_steps,
                feature_schema=FEATURE_SCHEMA_VERSION,
                training=stats.as_dict(),
            )
            _write_json(manifest_path, manifest.as_dict())
            manifests.append(manifest)
    return manifests


def evaluate_candidate(
    config: EvaluationConfig,
    *,
    tournament_fn: Callable[..., TournamentReport] = run_tournament,
) -> EvaluationResult:
    _validate_player_counts((config.player_count,))
    if config.games < 1:
        raise ValueError("games must be at least 1")
    previous_champion = _previous_champion_strategy(config.champions_path, config.player_count)
    strategies = _dedupe((config.candidate, *config.baselines, previous_champion))
    report = tournament_fn(
        player_count=config.player_count,
        games=config.games,
        strategy_names=strategies,
        seed=config.seed,
        max_turns=config.max_turns,
        max_self_play_steps=config.max_self_play_steps,
    )
    _require_tournament_summaries(report, strategies)
    scores = {name: _strategy_score(report, name) for name in report.summaries}
    return EvaluationResult(
        player_count=config.player_count,
        candidate=config.candidate,
        baselines=config.baselines,
        previous_champion=previous_champion,
        report=report,
        candidate_score=scores.get(config.candidate, 0.0),
        strategy_scores=scores,
    )


def load_champions_manifest(path: Path) -> dict[int, ChampionEntry | None]:
    if not path.exists():
        return {player_count: None for player_count in VALID_PLAYER_COUNTS}
    payload = json.loads(path.read_text(encoding="utf-8"))
    champions = payload.get("champions", {})
    entries: dict[int, ChampionEntry | None] = {}
    for player_count in VALID_PLAYER_COUNTS:
        entry_payload = champions.get(str(player_count))
        entries[player_count] = (
            None if entry_payload is None else _champion_entry_from_dict(entry_payload)
        )
    return entries


def write_champions_manifest(path: Path, entries: dict[int, ChampionEntry | None]) -> None:
    payload = {
        "feature_schema": FEATURE_SCHEMA_VERSION,
        "champions": {
            str(player_count): _champion_entry_to_json(entries.get(player_count))
            for player_count in VALID_PLAYER_COUNTS
        },
    }
    _write_json(path, payload)


def promote_champion(
    champions_path: Path,
    evaluation: EvaluationResult,
    *,
    checkpoint_path: str,
    metadata: dict[str, Any] | None = None,
    max_aborted_rate: float = 0.0,
) -> PromotionDecision:
    champions = load_champions_manifest(champions_path)
    current = champions[evaluation.player_count]
    blocker = _promotion_blocker(
        evaluation,
        current=current,
        max_aborted_rate=max_aborted_rate,
    )
    if blocker is not None:
        return PromotionDecision(promoted=False, reason=blocker)

    entry_metadata = dict(metadata or {})
    entry_metadata.update(
        {
            "candidate": evaluation.candidate,
            "promoted_at": datetime.now(UTC).isoformat(),
            "aborted_rate": evaluation.aborted_rate,
            "stalemate_rate": evaluation.stalemate_rate,
            "max_turn_rate": evaluation.max_turn_rate,
        }
    )
    champions[evaluation.player_count] = ChampionEntry(
        player_count=evaluation.player_count,
        checkpoint_path=checkpoint_path,
        evaluation_score=evaluation.candidate_score,
        metadata=entry_metadata,
    )
    write_champions_manifest(champions_path, champions)
    return PromotionDecision(promoted=True, reason="candidate promoted")


def _promotion_blocker(
    evaluation: EvaluationResult,
    *,
    current: ChampionEntry | None,
    max_aborted_rate: float,
) -> str | None:
    if evaluation.aborted_rate > max_aborted_rate:
        return (
            f"aborted rate {evaluation.aborted_rate:.2%} exceeds "
            f"limit {max_aborted_rate:.2%}"
        )
    baseline_scores = [
        evaluation.strategy_scores[baseline]
        for baseline in evaluation.baselines
        if baseline in evaluation.strategy_scores
    ]
    if baseline_scores and evaluation.candidate_score <= max(baseline_scores):
        return "candidate did not beat all baselines"
    if current is None:
        return None

    previous_score = evaluation.strategy_scores.get(_strategy_spec(current.checkpoint_path))
    if previous_score is None:
        return "current champion was not evaluated with the candidate"
    if evaluation.candidate_score <= previous_score:
        return "candidate did not beat the current champion"
    if _worse_outcome_profile(evaluation, current):
        return "candidate worsened champion outcome guardrails"
    return None


def _worse_outcome_profile(evaluation: EvaluationResult, current: ChampionEntry) -> bool:
    return (
        evaluation.stalemate_rate > float(current.metadata.get("stalemate_rate", 1.0))
        or evaluation.max_turn_rate > float(current.metadata.get("max_turn_rate", 1.0))
    )


def _strategy_score(report: TournamentReport, strategy: str) -> float:
    summary = report.summaries[strategy]
    rating = report.ratings.get(strategy, 1000.0)
    # Rating is the primary promotion/evaluation score; average rank breaks exact ties.
    return rating - summary.average_rank / 1000


def _require_tournament_summaries(report: TournamentReport, strategies: list[str]) -> None:
    missing = [strategy for strategy in strategies if strategy not in report.summaries]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"missing tournament summaries for: {joined}")


def _run_seed(base_seed: int, *, player_count: int, run_index: int) -> int:
    return base_seed + player_count * 1_000 + run_index - 1


def _previous_champion_strategy(path: Path | None, player_count: int) -> str | None:
    if path is None:
        return None
    entry = load_champions_manifest(path)[player_count]
    if entry is None:
        return None
    return _strategy_spec(entry.checkpoint_path)


def _strategy_spec(checkpoint_path: str) -> str:
    if checkpoint_path.startswith("neural:"):
        return checkpoint_path
    return f"neural:{checkpoint_path}"


def _dedupe(strategies: tuple[str | None, ...]) -> list[str]:
    deduped: list[str] = []
    for strategy in strategies:
        if strategy is not None and strategy not in deduped:
            deduped.append(strategy)
    return deduped


def _validate_player_counts(player_counts: tuple[int, ...]) -> None:
    invalid_count = any(player_count not in VALID_PLAYER_COUNTS for player_count in player_counts)
    if not player_counts or invalid_count:
        raise ValueError("player counts must be between 2 and 5")


def _champion_entry_to_json(entry: ChampionEntry | None) -> dict[str, Any] | None:
    if entry is None:
        return None
    return entry.as_dict()


def _champion_entry_from_dict(payload: dict[str, Any]) -> ChampionEntry:
    return ChampionEntry(
        player_count=int(payload["player_count"]),
        checkpoint_path=str(payload["checkpoint_path"]),
        evaluation_score=float(payload["evaluation_score"]),
        metadata=dict(payload.get("metadata", {})),
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

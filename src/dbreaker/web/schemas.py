from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NewGameRequest(BaseModel):
    player_count: int = Field(ge=2, le=5)
    human_player_id: str = "P1"
    ai_strategy: str = "basic"
    seed: int | None = None


class GameActionRequest(BaseModel):
    player_id: str
    expected_version: int
    action: dict[str, Any]


class AiStepRequest(BaseModel):
    expected_version: int
    max_steps: int = Field(default=10, ge=1, le=500)


class EvalJobRequest(BaseModel):
    candidate: str
    player_count: int = Field(ge=2, le=5)
    baselines: list[str] = Field(
        default_factory=lambda: [
            "basic",
            "aggressive",
            "defensive",
            "set_completion",
        ]
    )
    games: int = Field(default=2, ge=1, le=500)
    seed: int = 1
    max_turns: int = 200
    max_self_play_steps: int = 30_000
    champions_manifest_path: str | None = None
    promote_if_passes: bool = False
    max_aborted_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class TrainingJobRequest(BaseModel):
    player_count: int = Field(ge=2, le=5)
    games: int = Field(default=10, ge=1, le=10_000)
    rollout_batch_games: int = Field(
        default=50,
        ge=1,
        le=5000,
        description="Games per rollout before each PPO update (bounds RAM).",
    )
    seed: int = 1
    max_turns: int = 200
    max_self_play_steps: int = 30_000
    update_epochs: int = Field(default=2, ge=1, le=50)
    gamma: float = Field(default=0.99, ge=0.0, le=1.0)
    learning_rate: float = Field(default=3e-4, gt=0)
    clip_epsilon: float = Field(default=0.2, ge=0.0, le=1.0)
    value_coef: float = Field(default=0.5, ge=0.0)
    entropy_coef: float = Field(default=0.01, ge=0.0)
    opponent_mix_prob: float = Field(default=0.0, ge=0.0, le=1.0)
    opponent_strategies: list[str] = Field(
        default_factory=lambda: [
            "basic",
            "aggressive",
            "defensive",
            "set_completion",
        ]
    )
    champion_checkpoint_id: str | None = None
    resume_from_checkpoint_id: str | None = Field(
        default=None,
        description="Initial policy weights (continuation training; distinct from champion opponent pool).",
    )
    game_seed_offset: int = Field(
        default=0,
        ge=0,
        description="Added to per-game seeds; use cumulative prior games when batching training jobs.",
    )
    checkpoint_label: str | None = None


class RlSearchJobRequest(BaseModel):
    player_counts: list[int] = Field(
        default_factory=lambda: [2, 3, 4, 5],
        min_length=1,
    )
    runs_per_count: int = Field(default=1, ge=1, le=100)
    games_per_run: int = Field(default=10, ge=1, le=10_000)
    rollout_batch_games: int = Field(
        default=50,
        ge=1,
        le=5000,
        description="Games per rollout before each PPO update during rl-search.",
    )
    seed: int = 1
    max_turns: int = 200
    max_self_play_steps: int = 30_000
    update_epochs: int = Field(default=2, ge=1, le=50)
    gamma: float = Field(default=0.99, ge=0.0, le=1.0)
    opponent_mix_prob: float = Field(default=0.0, ge=0.0, le=1.0)
    opponent_strategies: list[str] = Field(
        default_factory=lambda: [
            "basic",
            "aggressive",
            "defensive",
            "set_completion",
        ]
    )
    champion_checkpoint_id: str | None = None


class TournamentJobRequest(BaseModel):
    player_count: int = Field(ge=2, le=5)
    games: int = Field(default=8, ge=1, le=2000)
    strategies: list[str] = Field(min_length=1)
    seed: int = 1
    max_turns: int = 200
    max_self_play_steps: int = 30_000


class ArtifactImportJobRequest(BaseModel):
    """Import and index checkpoint/manifest pairs under the artifact root."""

    rel_path: str = Field(
        description="Directory relative to artifact root, e.g. checkpoints/rl-search"
    )


class JobCreatedResponse(BaseModel):
    job_id: str
    status: str = "queued"
    links: dict[str, str]


class JobDetailResponse(BaseModel):
    job_id: str
    kind: str
    status: str
    config: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    log_path: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    links: dict[str, str]


class JobListResponse(BaseModel):
    items: list[JobDetailResponse]
    next_cursor: str | None = None


class GameListResponse(BaseModel):
    items: list[dict[str, Any]]


class ReplayListResponse(BaseModel):
    items: list[dict[str, Any]]


class CheckpointListResponse(BaseModel):
    items: list[dict[str, Any]]


class EvaluationListResponse(BaseModel):
    items: list[dict[str, Any]]


class ArtifactListResponse(BaseModel):
    items: list[dict[str, Any]]
    next_cursor: str | None = None


class ChampionsListResponse(BaseModel):
    items: list[dict[str, Any]]


class StrategiesResponse(BaseModel):
    built_in: list[str]
    neural_prefix: str = "neural:"
    hint: str = (
        "Use neural:<relative_or_absolute_checkpoint_path> for policy checkpoints."
    )


class LogSliceResponse(BaseModel):
    lines: list[str]
    offset: int
    end_offset: int

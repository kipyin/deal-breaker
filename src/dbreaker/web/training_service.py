from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from dbreaker.experiments.rl_search import VALID_PLAYER_COUNTS, RLSearchConfig
from dbreaker.ml.features import FEATURE_SCHEMA_VERSION
from dbreaker.ml.trainer import PPOConfig
from dbreaker.web.schemas import RlSearchJobRequest, TrainingJobRequest


def _safe_label(label: str | None, job_id: str) -> str:
    base = label or "train"
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "", base)[:32] or "train"
    return f"{safe}_{job_id[-8:]}"


def training_artifact_ids(
    job_id: str, player_count: int, label: str | None
) -> tuple[str, str, str]:
    """Return (checkpoint_id, rel_path_pt, rel_path_manifest)."""
    slug = _safe_label(label, job_id)
    ckpt_id = f"ckpt_{slug}"
    rel_base = f"checkpoints/{player_count}p"
    rel_pt = f"{rel_base}/{ckpt_id}.pt"
    rel_json = f"{rel_base}/{ckpt_id}.json"
    return ckpt_id, rel_pt, rel_json


def ppo_config_from_request(
    body: TrainingJobRequest,
    champion_checkpoint: Path | None,
    *,
    policy_pool_manifest: Path | None = None,
) -> PPOConfig:
    pk = body.policy_top_k
    policy_top_k = None if pk is None or pk == 0 else pk
    ppm_raw = getattr(body, "policy_pool_manifest_path", None)
    effective_pool = policy_pool_manifest or (Path(ppm_raw) if ppm_raw else None)
    return PPOConfig(
        games=body.games,
        rollout_batch_games=body.rollout_batch_games,
        rollout_target_steps=body.rollout_target_steps,
        min_rollout_games=body.min_rollout_games,
        player_count=body.player_count,
        max_turns=body.max_turns,
        max_self_play_steps=body.max_self_play_steps,
        learning_rate=body.learning_rate,
        clip_epsilon=body.clip_epsilon,
        value_coef=body.value_coef,
        entropy_coef=body.entropy_coef,
        update_epochs=body.update_epochs,
        gamma=body.gamma,
        opponent_mix_prob=body.opponent_mix_prob,
        opponent_strategies=tuple(body.opponent_strategies),
        champion_checkpoint=champion_checkpoint,
        policy_pool_manifest=effective_pool,
        opponent_neural_checkpoints=(),
        reward_terminal_rank_weight=body.reward_terminal_rank_weight,
        reward_completed_set_delta_weight=body.reward_completed_set_delta_weight,
        reward_asset_value_delta_weight=body.reward_asset_value_delta_weight,
        reward_rent_payment_delta_weight=body.reward_rent_payment_delta_weight,
        reward_opponent_completed_set_delta_weight=body.reward_opponent_completed_set_delta_weight,
        fast_single_learner=body.fast_single_learner,
        rollout_max_steps_per_game=body.rollout_max_steps_per_game,
        max_policy_actions=body.max_policy_actions,
        rollout_workers=body.rollout_workers,
        policy_top_k=policy_top_k,
    )


def write_training_manifest(
    rel_manifest: str, artifact_root: Path, training: dict[str, Any]
) -> None:
    path = artifact_root / rel_manifest
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "kind": "training",
        "feature_schema": FEATURE_SCHEMA_VERSION,
        "training": training,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def rl_search_config(
    body: RlSearchJobRequest,
    output_dir: Path,
    champion_checkpoint: Path | None,
    *,
    policy_pool_manifest: Path | None = None,
) -> RLSearchConfig:
    counts = tuple(body.player_counts)
    bad = [c for c in counts if c not in VALID_PLAYER_COUNTS]
    if bad:
        raise ValueError(
            f"invalid player_counts {bad}, expected subset of {list(VALID_PLAYER_COUNTS)}"
        )
    ppm_raw = getattr(body, "policy_pool_manifest_path", None)
    effective_pool = policy_pool_manifest or (
        Path(ppm_raw) if ppm_raw else None
    )
    return RLSearchConfig(
        output_dir=output_dir,
        player_counts=counts,
        runs_per_count=body.runs_per_count,
        games_per_run=body.games_per_run,
        rollout_batch_games=body.rollout_batch_games,
        rollout_target_steps=body.rollout_target_steps,
        min_rollout_games=body.min_rollout_games,
        seed=body.seed,
        max_turns=body.max_turns,
        max_self_play_steps=body.max_self_play_steps,
        update_epochs=body.update_epochs,
        gamma=body.gamma,
        opponent_mix_prob=body.opponent_mix_prob,
        opponent_strategies=tuple(body.opponent_strategies),
        champion_checkpoint=champion_checkpoint,
        policy_pool_manifest=effective_pool,
        fast_single_learner=body.fast_single_learner,
        rollout_max_steps_per_game=body.rollout_max_steps_per_game,
        max_policy_actions=body.max_policy_actions,
        rollout_workers=body.rollout_workers,
        policy_top_k=(
            None if body.policy_top_k is None or body.policy_top_k == 0 else body.policy_top_k
        ),
        telemetry_per_run=body.telemetry_per_run,
        structured_policy=body.structured_policy,
    )


__all__ = [
    "ppo_config_from_request",
    "rl_search_config",
    "training_artifact_ids",
    "write_training_manifest",
]

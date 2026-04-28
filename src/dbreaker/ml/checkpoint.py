from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dbreaker.ml.features import FEATURE_SCHEMA_VERSION
from dbreaker.ml.model import build_policy_from_config, require_torch


@dataclass(frozen=True, slots=True)
class LoadedCheckpoint:
    schema_version: str
    model: Any
    training_stats: dict[str, Any]
    optimizer_state: dict[str, Any] | None = None
    ppo_config: dict[str, Any] | None = None


def save_checkpoint(
    path: Path,
    *,
    model: Any,
    training_stats: dict[str, Any],
    optimizer_state: dict[str, Any] | None = None,
    ppo_config: dict[str, Any] | None = None,
) -> None:
    """Persist weights, training metadata, and optional optimizer / PPO resume state."""
    torch = require_torch()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "model_config": model.model_config(),
        "state_dict": model.state_dict(),
        "training_stats": training_stats,
    }
    if optimizer_state is not None:
        payload["optimizer_state"] = optimizer_state
    if ppo_config is not None:
        payload["ppo_config"] = ppo_config
    torch.save(payload, path)


def load_checkpoint(path: Path, *, map_location: Any = "cpu") -> LoadedCheckpoint:
    torch = require_torch()
    payload = torch.load(path, map_location=map_location)
    schema_version = str(payload["schema_version"])
    if schema_version != FEATURE_SCHEMA_VERSION:
        raise ValueError(
            f"checkpoint schema {schema_version!r} does not match {FEATURE_SCHEMA_VERSION!r}"
        )
    model = build_policy_from_config(payload["model_config"])
    model.load_state_dict(payload["state_dict"])
    model.eval()
    stats = dict(payload.get("training_stats", {}))
    opt_state = payload.get("optimizer_state")
    opt_out: dict[str, Any] | None = None if opt_state is None else dict(opt_state)
    ppo_cfg = payload.get("ppo_config")
    ppo_out: dict[str, Any] | None = None if ppo_cfg is None else dict(ppo_cfg)
    return LoadedCheckpoint(
        schema_version=schema_version,
        model=model,
        training_stats=stats,
        optimizer_state=opt_out,
        ppo_config=ppo_out,
    )

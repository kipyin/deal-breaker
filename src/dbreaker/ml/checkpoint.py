from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dbreaker.ml.features import FEATURE_SCHEMA_VERSION
from dbreaker.ml.model import PolicyValueNetwork, require_torch


@dataclass(frozen=True, slots=True)
class LoadedCheckpoint:
    schema_version: str
    model: PolicyValueNetwork
    training_stats: dict[str, Any]


def save_checkpoint(
    path: Path,
    *,
    model: PolicyValueNetwork,
    training_stats: dict[str, Any],
) -> None:
    """Persist weights and training metadata (includes ``schema_version`` and ``model_config`` dims).

    Checkpoints are suitable for continuation training (load weights; Adam state is not stored,
    so each run starts a fresh optimizer). Feature schema v2 is incompatible with v1 checkpoints.
    """
    torch = require_torch()
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema_version": FEATURE_SCHEMA_VERSION,
            "model_config": model.model_config(),
            "state_dict": model.state_dict(),
            "training_stats": training_stats,
        },
        path,
    )


def load_checkpoint(path: Path) -> LoadedCheckpoint:
    torch = require_torch()
    payload = torch.load(path, map_location="cpu")
    schema_version = str(payload["schema_version"])
    if schema_version != FEATURE_SCHEMA_VERSION:
        raise ValueError(
            f"checkpoint schema {schema_version!r} does not match {FEATURE_SCHEMA_VERSION!r}"
        )
    model = PolicyValueNetwork(**payload["model_config"])
    model.load_state_dict(payload["state_dict"])
    model.eval()
    stats = dict(payload.get("training_stats", {}))
    return LoadedCheckpoint(schema_version=schema_version, model=model, training_stats=stats)

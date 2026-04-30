"""Policy pool manifest: multiple checkpoints per player count for opponent sampling."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


POOL_SCHEMA_REVISION = "2026.pool-v1"


@dataclass(frozen=True, slots=True)
class PolicyPoolEntry:
    """One neural opponent checkpoint entry (optional metadata for bookkeeping)."""

    checkpoint_path: str
    player_count: int
    weight: float = 1.0
    generation: int = 0
    tags: tuple[str, ...] = ()
    evaluation_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def load_policy_pool(path: Path) -> tuple[PolicyPoolEntry, ...]:
    if not path.is_file():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    revision = payload.get("schema_revision", "?")
    if revision != POOL_SCHEMA_REVISION:
        raise ValueError(f"unsupported policy_pool schema_revision {revision!r}")
    raw = payload.get("entries") or ()
    entries: list[PolicyPoolEntry] = []
    for item in raw:
        if isinstance(item.get("checkpoint_path"), str) and isinstance(item.get("player_count"), int):
            md = dict(item["metadata"]) if isinstance(item.get("metadata"), dict) else {}
            tags = tuple(str(t) for t in item["tags"]) if isinstance(item.get("tags"), list) else ()
            entries.append(
                PolicyPoolEntry(
                    checkpoint_path=item["checkpoint_path"],
                    player_count=int(item["player_count"]),
                    weight=float(item.get("weight", 1.0)),
                    generation=int(item.get("generation", 0)),
                    tags=tags,
                    evaluation_score=float(item["evaluation_score"]) if item.get("evaluation_score") is not None else None,
                    metadata=md,
                ),
            )
    return tuple(entries)


def write_policy_pool(path: Path, entries: Sequence[PolicyPoolEntry]) -> None:
    payload = {
        "schema_revision": POOL_SCHEMA_REVISION,
        "entries": [_entry_as_json(e) for e in entries],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _entry_as_json(entry: PolicyPoolEntry) -> dict[str, Any]:
    return {
        "checkpoint_path": entry.checkpoint_path,
        "player_count": entry.player_count,
        "weight": entry.weight,
        "generation": entry.generation,
        "tags": list(entry.tags),
        "evaluation_score": entry.evaluation_score,
        "metadata": dict(entry.metadata),
    }


def entries_for_player_count(entries: Sequence[PolicyPoolEntry], player_count: int) -> tuple[PolicyPoolEntry, ...]:
    return tuple(e for e in entries if e.player_count == player_count)


def strategy_spec(entry: PolicyPoolEntry) -> str:
    """Build `neural:...` spec for tournament/registry."""
    return f"neural:{entry.checkpoint_path}"


def sample_weighted_opponent_specs(
    *,
    heuristic_names: tuple[str, ...],
    champion_checkpoint: Path | None,
    pool_entries_for_count: Sequence[PolicyPoolEntry],
    rng: random.Random,
) -> tuple[tuple[str, float], ...]:
    """Return (spec string, positive weight) rows for softmax-free weighted RNG."""
    items: list[tuple[str, float]] = [(name, 1.0) for name in heuristic_names]
    if champion_checkpoint is not None:
        items.append((f"neural:{champion_checkpoint}", 1.0))
    for e in pool_entries_for_count:
        w = float(e.weight) if e.weight > 0 else 1.0
        items.append((strategy_spec(e), w))
    return tuple(items)


def pick_opponent_strategy(rng: random.Random, items: Sequence[tuple[str, float]]) -> str:
    specs = [spec for spec, _ in items]
    weights = [float(w) for _, w in items]
    s = sum(weights)
    if s <= 0:
        raise ValueError("opponent sampling weights sum to zero")
    return rng.choices(specs, weights=weights, k=1)[0]


def pick_pool_evaluation_specs(
    entries: Sequence[PolicyPoolEntry],
    *,
    candidate_spec: str,
    count: int,
    seed: int,
) -> tuple[str, ...]:
    """Return up to `count` distinct neural pool specs for gauntlets, excluding the candidate."""
    if count < 1 or not entries:
        return ()
    # Stable dedupe candidate path substring
    c_norm = _normalize_neural(candidate_spec)
    candidates: list[PolicyPoolEntry] = []
    seen: set[str] = set()
    for e in entries:
        spec = strategy_spec(e)
        n = _normalize_neural(spec)
        if n == c_norm:
            continue
        if spec in seen:
            continue
        seen.add(spec)
        candidates.append(e)
    if not candidates:
        return ()
    rng = random.Random(seed + 17_917)
    k = min(count, len(candidates))
    picks = rng.sample(candidates, k=k)
    return tuple(strategy_spec(p) for p in picks)


def _normalize_neural(spec: str) -> str:
    if spec.startswith("neural:"):
        return Path(spec.split(":", 1)[1]).resolve().as_posix()
    return Path(spec).resolve().as_posix()


def merge_pool_entries(
    previous: Sequence[PolicyPoolEntry],
    new_entries: Sequence[PolicyPoolEntry],
) -> tuple[PolicyPoolEntry, ...]:
    """Union by (checkpoint_path, player_count); later entries overwrite weight/metadata."""

    keyed: dict[tuple[str, int], PolicyPoolEntry] = {}
    for e in (*previous, *new_entries):
        keyed[(e.checkpoint_path, e.player_count)] = e
    return tuple(sorted(keyed.values(), key=lambda x: (x.player_count, x.checkpoint_path)))


def load_policy_pool_per_player(path: Path, player_count: int) -> tuple[PolicyPoolEntry, ...]:
    return entries_for_player_count(load_policy_pool(path), player_count)


def pool_entries_to_ppo_weights(
    entries: Sequence[PolicyPoolEntry],
) -> tuple[tuple[Path, float], ...]:
    """Map manifest entries into ``(checkpoint_path, weight)`` tuples for training."""
    out: list[tuple[Path, float]] = []
    for e in entries:
        out.append((Path(e.checkpoint_path), float(e.weight) if e.weight > 0 else 1.0))
    return tuple(out)


def neural_strategy_spec(checkpoint_path: str) -> str:
    return f"neural:{checkpoint_path}"


def sample_pool_entries_without_replacement(
    entries: Sequence[PolicyPoolEntry],
    count: int,
    rng: random.Random,
) -> tuple[PolicyPoolEntry, ...]:
    if count < 1 or not entries:
        return ()
    k = min(count, len(entries))
    picks = rng.sample(list(entries), k=k)
    return tuple(picks)


def append_policy_pool_entry(path: Path, entry: PolicyPoolEntry) -> None:
    merged = merge_pool_entries(load_policy_pool(path), (entry,))
    write_policy_pool(path, merged)


def merge_training_neural_weights(
    *,
    champion_checkpoint: Path | None,
    policy_pool_manifest: Path | None,
    player_count: int,
) -> tuple[tuple[Path, float], ...]:
    """Merge champion + filtered policy-pool weights for opponent sampling.

    Duplicate checkpoint paths accumulate weight (max of both when present twice).
    """
    rows: dict[Path, float] = {}
    if champion_checkpoint is not None:
        p = Path(champion_checkpoint).resolve()
        rows[p] = rows.get(p, 0.0) + 1.0
    if policy_pool_manifest is not None:
        for e in entries_for_player_count(load_policy_pool(policy_pool_manifest), player_count):
            p = Path(e.checkpoint_path).resolve()
            rows[p] = rows.get(p, 0.0) + max(e.weight, 1e-9)
    return tuple(sorted(rows.items(), key=lambda kv: str(kv[0])))

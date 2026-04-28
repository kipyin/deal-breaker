"""Human-readable summaries from training metrics, checkpoints, and telemetry JSONL."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_metrics_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def telemetry_action_histogram(path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            counts[str(row.get("action_type", "?"))] += 1
    return counts


def render_strategy_summary_text(
    *,
    metrics: dict[str, Any] | None = None,
    checkpoint_payload: dict[str, Any] | None = None,
    telemetry_path: Path | None = None,
) -> str:
    lines: list[str] = ["Strategy / training summary", ""]

    if metrics:
        lines.append("Training metrics (TrainingStats)")
        lines.append(f"  games={metrics.get('games')} steps={metrics.get('steps')}")
        lines.append(f"  mean_reward={metrics.get('mean_reward')}")
        if metrics.get("ppo_updates") is not None:
            lines.append(f"  ppo_updates={metrics.get('ppo_updates')}")
        if metrics.get("mean_entropy") is not None:
            lines.append(f"  mean_entropy={metrics.get('mean_entropy')}")
        if metrics.get("continued_from"):
            lines.append(f"  continued_from={metrics.get('continued_from')}")
        eb = metrics.get("ended_by")
        if isinstance(eb, dict):
            lines.append(f"  ended_by={dict(eb)}")
        lines.append("")

    if checkpoint_payload is not None:
        lines.append("Checkpoint manifest")
        mc = checkpoint_payload.get("model_config") or {}
        lines.append(f"  model kind={mc.get('kind', '?')}")
        ppo = checkpoint_payload.get("ppo_config")
        if isinstance(ppo, dict):
            lines.append(
                f"  ppo: lr={ppo.get('learning_rate')} rollout_workers={ppo.get('rollout_workers')}"
            )
        ts = checkpoint_payload.get("training_stats")
        if isinstance(ts, dict) and ts:
            lines.append(f"  training_stats.games={ts.get('games')}")
        lines.append("")

    if telemetry_path is not None:
        hist = telemetry_action_histogram(telemetry_path)
        total = sum(hist.values())
        lines.append(f"Telemetry JSONL ({telemetry_path.name}) lines={total}")
        for name, count in hist.most_common(24):
            lines.append(f"  {name}: {count}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def checkpoint_payload_dict(path: Path) -> dict[str, Any]:
    """Load raw checkpoint payload without restoring nn.Module (requires torch)."""
    from dbreaker.ml.model import require_torch

    torch = require_torch()
    return dict(torch.load(path, map_location="cpu"))

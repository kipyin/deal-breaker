"""Human-readable summaries from training metrics, checkpoints, and telemetry JSONL."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from dbreaker.experiments.eval_protocol import EVAL_PROTOCOL_REVISION, GAUNTLET_PROTOCOL_REVISION


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


def telemetry_phase_histogram(path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            ph = row.get("phase")
            counts[str(ph if ph is not None else "?")] += 1
    return counts


def telemetry_phase_action_cross(path: Path, *, limit: int = 12) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            a = row.get("action_type", "?")
            p = row.get("phase", "?")
            key = f"{p} / {a}"
            counts[key] += 1
    return counts.most_common(limit)


def _safe_float(val: Any) -> str:
    try:
        return f"{float(val):.6f}"
    except (TypeError, ValueError):
        return str(val)


def render_strategy_summary_text(
    *,
    metrics: dict[str, Any] | None = None,
    checkpoint_payload: dict[str, Any] | None = None,
    telemetry_path: Path | None = None,
) -> str:
    """Emit Markdown-ish text: training stats, optional PPO/reward shaping, telemetry rollups."""
    lines: list[str] = ["# Strategy report 2.0", ""]

    lines.append("## Learning process")
    lines.append("")
    if metrics:
        lines.append("*Training metrics* (``TrainingStats`` payload)")
        lines.append(f"- games=`{metrics.get('games')}` steps=`{metrics.get('steps')}`")
        lines.append(f"- mean_reward=`{_safe_float(metrics.get('mean_reward'))}`")
        if metrics.get("ppo_updates") is not None:
            lines.append(f"- ppo_updates=`{metrics.get('ppo_updates')}`")
        if metrics.get("mean_entropy") is not None:
            lines.append(f"- mean_entropy=`{_safe_float(metrics.get('mean_entropy'))}`")
        if metrics.get("continued_from"):
            lines.append(f"- continued_from=`{metrics.get('continued_from')}`")
        eb = metrics.get("ended_by")
        if isinstance(eb, dict):
            lines.append(f"- ended_by={dict(eb)}")
        rc = metrics.get("reward_component_means")
        if isinstance(rc, dict) and rc:
            lines.append("- reward_component_means (mean per learner step, raw telemetry sums):")
            for key in sorted(rc.keys()):
                lines.append(f"  - `{key}`: {_safe_float(rc[key])}")
        elif metrics.get("reward_component_means") is None:
            lines.append("- reward_component_means: _not present (legacy metrics JSON)._")
        lines.append("")
    else:
        lines.append("_No `--metrics` JSON provided._")
        lines.append("")

    lines.append("## Checkpoint & protocols")
    lines.append("")
    if checkpoint_payload is not None:
        lines.append("*Checkpoint manifest* (torch payload)")
        mc = checkpoint_payload.get("model_config") or {}
        lines.append(f"- model kind=`{mc.get('kind', '?')}`")
        ppo = checkpoint_payload.get("ppo_config")
        if isinstance(ppo, dict):
            lines.append(
                f"- PPO: lr=`{ppo.get('learning_rate')}` rollout_workers="
                f"`{ppo.get('rollout_workers')}` gamma=`{ppo.get('gamma')}`"
            )
            rw = [
                ("reward_terminal_rank_weight", ppo.get("reward_terminal_rank_weight")),
                ("reward_completed_set_delta_weight", ppo.get("reward_completed_set_delta_weight")),
                ("reward_asset_value_delta_weight", ppo.get("reward_asset_value_delta_weight")),
                ("reward_rent_payment_delta_weight", ppo.get("reward_rent_payment_delta_weight")),
                ("reward_opponent_completed_set_delta_weight", ppo.get("reward_opponent_completed_set_delta_weight")),
            ]
            if any(v is not None for _, v in rw):
                lines.append("- reward weights (0 = off):")
                for name, val in rw:
                    if val is not None:
                        lines.append(f"  - `{name}`: {val}")
            onc = ppo.get("opponent_neural_checkpoints")
            if onc:
                lines.append(f"- opponent_neural_checkpoints: `{onc!r}`")
        ts = checkpoint_payload.get("training_stats")
        if isinstance(ts, dict) and ts:
            lines.append(f"- training_stats.games=`{ts.get('games')}`")
        lines.append("")
        lines.append(
            f"_Doc revisions: eval `{EVAL_PROTOCOL_REVISION}`, "
            f"gauntlet `{GAUNTLET_PROTOCOL_REVISION}`._"
        )
        lines.append("")
    else:
        lines.append("_No `--checkpoint` provided._")
        lines.append("")

    lines.append("## Playstyle & telemetry")
    lines.append("")
    if telemetry_path is not None:
        try:
            hist = telemetry_action_histogram(telemetry_path)
            total = sum(hist.values())
            lines.append(f"*Telemetry JSONL* (`{telemetry_path.name}`), lines≈`{total}`")
            lines.append("")
            lines.append("| action_type | approx_count |")
            lines.append("|---|---:|")
            for name, count in hist.most_common(20):
                lines.append(f"| {name} | {count} |")
            lines.append("")
            ph_hist = telemetry_phase_histogram(telemetry_path)
            if ph_hist:
                lines.append("| phase | approx_count |")
                lines.append("|---|---:|")
                for name, count in ph_hist.most_common(12):
                    lines.append(f"| {name} | {count} |")
                lines.append("")
            cross = telemetry_phase_action_cross(telemetry_path, limit=10)
            if cross:
                lines.append("| phase / action | count |")
                lines.append("|---|---:|")
                for label, cnt in cross:
                    lines.append(f"| {label} | {cnt} |")
                lines.append("")
            lines.append(
                "_If `rent_payment_delta` is absent, shaping for rent/payments is not "
                "observed yet (see `reward_telemetry_gaps` in raw JSONL)._"
            )
            lines.append("")
        except OSError:
            lines.append("_Could not read telemetry file._")
            lines.append("")
    else:
        lines.append("_No `--telemetry` JSONL provided._")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def checkpoint_payload_dict(path: Path) -> dict[str, Any]:
    """Load raw checkpoint payload without restoring nn.Module (requires torch)."""
    from dbreaker.ml.model import require_torch

    torch = require_torch()
    return dict(torch.load(path, map_location="cpu"))

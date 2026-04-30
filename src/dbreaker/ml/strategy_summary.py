"""Aggregate training artifacts into a short readability report."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_training_metrics(
    *,
    metrics: dict[str, Any],
    checkpoint_note: str | None = None,
) -> list[str]:
    """Return Markdown-friendly lines summarizing TrainingStats payloads."""
    lines: list[str] = []
    lines.append("# Strategy summary (training)")
    lines.append("")
    if checkpoint_note:
        lines.append(f"*Checkpoint note:* `{checkpoint_note}`")
        lines.append("")
    games = metrics.get("games")
    steps = metrics.get("steps")
    mean_reward = metrics.get("mean_reward")
    if games is not None:
        lines.append(f"- Training games covered: `{games}`")
    if steps is not None:
        lines.append(f"- Total learner steps: `{steps}`")
    if mean_reward is not None:
        lines.append(f"- Mean learner reward/step: `{float(mean_reward):.4f}`")
    entropy = metrics.get("mean_entropy")
    if entropy is not None:
        lines.append(f"- Mean policy entropy (PPO epochs): `{float(entropy):.4f}`")
    ended_by = metrics.get("ended_by")
    if isinstance(ended_by, dict) and ended_by:
        eb = ", ".join(f"`{k}`={v}" for k, v in sorted(ended_by.items()))
        lines.append(f"- Outcome buckets: {eb}")
    rc = metrics.get("reward_component_means")
    if isinstance(rc, dict) and rc:
        lines.append("- Reward shaping telemetry (mean per learner step):")
        for key in sorted(rc.keys()):
            lines.append(f"  - `{key}`: `{float(rc[key]):.6f}`")
    device = metrics.get("training_device")
    if isinstance(device, str) and device:
        lines.append(f"- Device: `{device}`")
    rollout_s = metrics.get("rollout_seconds")
    ppo_s = metrics.get("ppo_update_seconds")
    if isinstance(rollout_s, int | float) and isinstance(ppo_s, int | float):
        lines.append(
            f"- Wall time (approx): rollout `{float(rollout_s):.2f}s`, "
            f"PPO `{float(ppo_s):.2f}s`, total `{float(metrics.get('total_seconds') or 0):.2f}s`."
        )
    return lines


def count_action_histogram(telemetry_objects: list[dict[str, Any]]) -> Counter[str]:
    hist: Counter[str] = Counter()
    for obj in telemetry_objects:
        typ = obj.get("action_type")
        if isinstance(typ, str):
            hist[typ] += 1
    return hist


def summarize_telemetry_lines(path: Path) -> list[str]:
    telemetry: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            telemetry.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    lines = ["## Telemetry rollups", ""]
    if not telemetry:
        lines.append("_No telemetry lines parsed._")
        return lines
    hist = count_action_histogram(telemetry)
    lines.append("| ActionKind | ApproxCount |")
    lines.append("|------------|------------:|")
    for name, cnt in hist.most_common():
        lines.append(f"| {name} | {cnt} |")
    phases = Counter(
        obj["phase"]
        for obj in telemetry
        if isinstance(obj.get("phase"), str)
    )
    if phases:
        lines.append("")
        lines.append("| GamePhase | Count |")
        lines.append("|-----------|------:|")
        for phase, cnt in phases.most_common():
            lines.append(f"| {phase} | {cnt} |")
    lines.append("")
    return lines


def render_strategy_summary(
    *,
    metrics_json: Path | None = None,
    telemetry_jsonl: Path | None = None,
    checkpoint_note: str | None = None,
) -> str:
    chunks: list[str] = []
    if metrics_json is not None:
        payload = _load_json(metrics_json)
        if isinstance(payload.get("training"), dict):
            chunks.extend(
                summarize_training_metrics(
                    metrics=payload["training"],
                    checkpoint_note=payload.get("checkpoint_id"),  # type: ignore[arg-type]
                ),
            )
        else:
            chunks.extend(
                summarize_training_metrics(
                    metrics=payload,
                    checkpoint_note=checkpoint_note,
                ),
            )
        chunks.append("")
    if telemetry_jsonl is not None:
        chunks.extend(summarize_telemetry_lines(telemetry_jsonl))
    return "\n".join(chunks).strip() + "\n"

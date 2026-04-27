from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dbreaker.ml.features import FEATURE_SCHEMA_VERSION
from dbreaker.web import db as db_mod
from dbreaker.web.config import WebConfig


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rel_under_root(root: Path, p: Path) -> str:
    p = p.resolve()
    r = root.resolve()
    return str(p.relative_to(r))


def index_checkpoint_path(
    conn: sqlite3.Connection,
    *,
    rel_path: str,
    job_id: str | None,
    label: str | None,
    strategy_spec: str,
    training_stats: dict[str, Any],
    manifest_path: str | None,
    schema_version: str | None = None,
    checkpoint_id: str | None = None,
) -> str:
    """Insert checkpoint row if new; return checkpoint id."""
    existing = db_mod.get_checkpoint_by_path(conn, rel_path)
    if existing is not None:
        return existing.id

    ckpt_id = checkpoint_id or db_mod.new_checkpoint_id()
    player_count: int | None = None
    for part in rel_path.split("/"):
        if part.endswith("p") and part[:-1].isdigit():
            player_count = int(part[:-1])
            break
    db_mod.insert_checkpoint(
        conn,
        checkpoint_id=ckpt_id,
        path=rel_path,
        label=label,
        player_count=player_count,
        source_job_id=job_id,
        schema_version=schema_version or FEATURE_SCHEMA_VERSION,
        strategy_spec=strategy_spec,
        training_stats=training_stats,
        manifest_path=manifest_path,
    )
    meta = {
        "player_count": player_count,
        "strategy_spec": strategy_spec,
        "training_stats": training_stats,
    }
    art_id = db_mod.new_artifact_id()
    db_mod.insert_artifact(
        conn,
        artifact_id=art_id,
        kind="checkpoint",
        rel_path=rel_path,
        label=label,
        job_id=job_id,
        checkpoint_id=ckpt_id,
        metadata=meta,
    )
    if manifest_path:
        art_m = db_mod.new_artifact_id()
        mmeta: dict[str, Any] = {
            "checkpoint_id": ckpt_id,
            "companion": rel_path,
        }
        db_mod.insert_artifact(
            conn,
            artifact_id=art_m,
            kind="manifest",
            rel_path=manifest_path,
            label=label,
            job_id=job_id,
            checkpoint_id=ckpt_id,
            metadata=mmeta,
        )
    return ckpt_id


def import_rl_search_tree(
    config: WebConfig, conn: sqlite3.Connection, rel_dir: str
) -> list[str]:
    """
    Index ``run-NNN.pt`` and ``run-NNN.json`` under e.g. ``checkpoints/rl-search/4p/``.
    Returns new checkpoint ids.
    """
    base = (config.artifact_root / rel_dir).resolve()
    if not base.is_dir():
        raise FileNotFoundError(f"import directory missing: {base}")

    ts = _utc_now()
    new_ids: list[str] = []
    for pt in sorted(base.rglob("run-*.pt")):
        rel = _rel_under_root(config.artifact_root, pt)
        if db_mod.get_checkpoint_by_path(conn, rel) is not None:
            continue
        jpath = pt.with_suffix(".json")
        manifest_rel: str | None
        if jpath.is_file():
            manifest_rel = _rel_under_root(config.artifact_root, jpath)
        else:
            manifest_rel = None
        label = pt.stem
        try:
            training_stats: dict[str, Any] = (
                json.loads(jpath.read_text(encoding="utf-8"))
                if jpath.is_file()
                else {}
            )
        except (OSError, json.JSONDecodeError):
            training_stats = {}
        strategy_spec = f"neural:{rel}"
        schema = str(training_stats.get("feature_schema", "")) or None
        ckpt_id = index_checkpoint_path(
            conn,
            rel_path=rel,
            job_id=None,
            label=label,
            strategy_spec=strategy_spec,
            training_stats=training_stats if training_stats else {"imported": True},
            manifest_path=manifest_rel,
            schema_version=schema,
        )
        new_ids.append(ckpt_id)
        arow = conn.execute(
            "select id from artifacts where rel_path = ?",
            (rel,),
        ).fetchone()
        if arow is not None:
            conn.execute(
                "update artifacts set imported_at = ? where id = ?",
                (ts, arow["id"]),
            )
            conn.commit()
    return new_ids

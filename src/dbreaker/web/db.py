from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


SCHEMA_VERSION = "1"
MIGRATION_V2 = "2"


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _apply_v2_schema(conn: sqlite3.Connection) -> None:
    if (
        conn.execute(
            "select 1 from schema_migrations where version = ?",
            (MIGRATION_V2,),
        ).fetchone()
        is not None
    ):
        return
    conn.executescript(
        """
        create table if not exists checkpoints (
          id text primary key,
          path text not null unique,
          label text,
          player_count integer,
          source_job_id text references jobs(id),
          schema_version text,
          strategy_spec text not null,
          training_stats_json text not null,
          manifest_path text,
          promoted integer not null default 0,
          created_at text not null
        );

        create table if not exists evaluations (
          id text primary key,
          job_id text references jobs(id),
          candidate_spec text not null,
          player_count integer not null,
          baselines_json text not null,
          games integer not null,
          seed integer not null,
          report_json text not null,
          candidate_score real not null,
          strategy_scores_json text not null,
          promoted integer,
          promotion_reason text,
          created_at text not null
        );

        create table if not exists metric_summaries (
          id text primary key,
          subject_type text not null check (subject_type in (
            'job', 'game', 'checkpoint', 'evaluation'
          )),
          subject_id text not null,
          name text not null,
          value real not null,
          unit text,
          metadata_json text not null,
          created_at text not null
        );

        create table if not exists artifacts (
          id text primary key,
          kind text not null check (kind in (
            'checkpoint', 'manifest', 'replay', 'job_log',
            'evaluation_report', 'import', 'other', 'tournament_report'
          )),
          rel_path text not null unique,
          label text,
          job_id text references jobs(id),
          checkpoint_id text references checkpoints(id) on delete set null,
          metadata_json text not null,
          created_at text not null,
          imported_at text
        );

        create index if not exists checkpoints_player_count
          on checkpoints(player_count);
        create index if not exists checkpoints_source_job
          on checkpoints(source_job_id);
        create index if not exists evaluations_candidate_spec
          on evaluations(candidate_spec);
        create index if not exists evaluations_job_id on evaluations(job_id);
        create index if not exists metric_summaries_subject
          on metric_summaries(subject_type, subject_id);
        create index if not exists artifacts_kind on artifacts(kind);
        create index if not exists artifacts_job_id on artifacts(job_id);
        """
    )
    conn.execute(
        "insert into schema_migrations (version, applied_at) values (?, ?)",
        (MIGRATION_V2, _utc_now()),
    )


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists schema_migrations (
          version text primary key,
          applied_at text not null
        );

        create table if not exists jobs (
          id text primary key,
          kind text not null check (kind in (
            'play_session', 'training', 'rl_search', 'evaluation',
            'tournament', 'artifact_import'
          )),
          status text not null check (status in (
            'queued', 'running', 'succeeded', 'failed', 'cancelled'
          )),
          config_json text not null,
          result_json text,
          error text,
          log_path text,
          created_at text not null,
          started_at text,
          finished_at text,
          updated_at text not null
        );

        create table if not exists games (
          id text primary key,
          source text not null check (source in ('live', 'scripted', 'self_play', 'imported')),
          job_id text references jobs(id),
          player_count integer not null,
          seed integer,
          strategy_specs_json text not null,
          status text not null check (status in ('active', 'completed', 'aborted')),
          winner_id text,
          ended_by text,
          turn_count integer not null default 0,
          replay_path text,
          action_log_json text,
          created_at text not null,
          finished_at text
        );

        create table if not exists replays (
          id text primary key,
          game_id text references games(id),
          path text not null unique,
          event_count integer not null default 0,
          first_turn integer,
          last_turn integer,
          imported_at text not null,
          metadata_json text not null
        );

        create index if not exists jobs_status_created_at on jobs(status, created_at);
        create index if not exists games_job_id on games(job_id);
        create index if not exists replays_game_id on replays(game_id);
        """
    )
    row = conn.execute(
        "select 1 from schema_migrations where version = ?", (SCHEMA_VERSION,)
    ).fetchone()
    if row is None:
        conn.execute(
            "insert into schema_migrations (version, applied_at) values (?, ?)",
            (SCHEMA_VERSION, _utc_now()),
        )
    _apply_v2_schema(conn)
    conn.commit()


@dataclass(slots=True)
class JobRow:
    id: str
    kind: str
    status: str
    config_json: str
    result_json: str | None
    error: str | None
    log_path: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    updated_at: str

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.id,
            "kind": self.kind,
            "status": self.status,
            "config": json.loads(self.config_json),
            "result": json.loads(self.result_json) if self.result_json else None,
            "error": self.error,
            "log_path": self.log_path,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "links": {
                "self": f"/api/jobs/{self.id}",
                "logs": f"/api/jobs/{self.id}/logs",
            },
        }


def insert_job(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    kind: str,
    config: dict[str, Any],
    log_path: str | None,
) -> None:
    now = _utc_now()
    conn.execute(
        """
        insert into jobs (
          id, kind, status, config_json, result_json, error, log_path,
          created_at, started_at, finished_at, updated_at
        ) values (?, ?, 'queued', ?, null, null, ?, ?, null, null, ?)
        """,
        (job_id, kind, json.dumps(config), log_path, now, now),
    )
    conn.commit()


def update_job_status(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    now = _utc_now()
    fields: list[str] = ["status = ?", "updated_at = ?"]
    args: list[Any] = [status, now]
    if status == "running":
        fields.append("started_at = coalesce(started_at, ?)")
        args.append(now)
    if status in {"succeeded", "failed", "cancelled"}:
        fields.append("finished_at = ?")
        args.append(now)
    if result is not None:
        fields.append("result_json = ?")
        args.append(json.dumps(result))
    if error is not None:
        fields.append("error = ?")
        args.append(error)
    args.append(job_id)

    # Validate fragments to prevent SQL injection via f-string join
    allowed = {
        "status = ?",
        "updated_at = ?",
        "started_at = coalesce(started_at, ?)",
        "finished_at = ?",
        "result_json = ?",
        "error = ?",
    }
    for f in fields:
        if f not in allowed:
            raise ValueError(f"Forbidden field update: {f}")

    conn.execute(f"update jobs set {', '.join(fields)} where id = ?", args)
    conn.commit()


def get_job(conn: sqlite3.Connection, job_id: str) -> JobRow | None:
    row = conn.execute("select * from jobs where id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    return JobRow(
        id=row["id"],
        kind=row["kind"],
        status=row["status"],
        config_json=row["config_json"],
        result_json=row["result_json"],
        error=row["error"],
        log_path=row["log_path"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        updated_at=row["updated_at"],
    )


def list_jobs(
    conn: sqlite3.Connection,
    *,
    limit: int = 20,
    offset: int = 0,
    kind: str | None = None,
    status: str | None = None,
) -> Iterator[JobRow]:
    where: list[str] = []
    args: list[Any] = []
    if kind is not None:
        where.append("kind = ?")
        args.append(kind)
    if status is not None:
        where.append("status = ?")
        args.append(status)
    q = "select * from jobs"
    if where:
        allowed = {"kind = ?", "status = ?"}
        for w in where:
            if w not in allowed:
                raise ValueError(f"Forbidden where clause: {w}")
        q += " where " + " and ".join(where)
    q += " order by created_at desc limit ? offset ?"
    args.extend([limit, offset])
    for row in conn.execute(q, args):
        yield JobRow(
            id=row["id"],
            kind=row["kind"],
            status=row["status"],
            config_json=row["config_json"],
            result_json=row["result_json"],
            error=row["error"],
            log_path=row["log_path"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            updated_at=row["updated_at"],
        )


def insert_game(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    source: str,
    player_count: int,
    seed: int | None,
    strategy_specs: dict[str, Any],
) -> None:
    now = _utc_now()
    conn.execute(
        """
        insert into games (
          id, source, job_id, player_count, seed, strategy_specs_json,
          status, winner_id, ended_by, turn_count, replay_path, action_log_json,
          created_at, finished_at
        ) values (?, ?, null, ?, ?, ?, 'active', null, null, 0, null, null, ?, null)
        """,
        (game_id, source, player_count, seed, json.dumps(strategy_specs), now),
    )
    conn.commit()


def update_game_complete(
    conn: sqlite3.Connection,
    game_id: str,
    *,
    status: str,
    winner_id: str | None,
    ended_by: str | None,
    turn_count: int,
    replay_path: str | None,
    action_log_json: str | None,
) -> None:
    now = _utc_now()
    conn.execute(
        """
        update games set
          status = ?, winner_id = ?, ended_by = ?, turn_count = ?,
          replay_path = ?, action_log_json = ?, finished_at = ?
        where id = ?
        """,
        (status, winner_id, ended_by, turn_count, replay_path, action_log_json, now, game_id),
    )
    conn.commit()


def insert_replay(
    conn: sqlite3.Connection,
    *,
    replay_id: str,
    game_id: str,
    path: str,
    event_count: int,
    first_turn: int | None,
    last_turn: int | None,
    metadata: dict[str, Any],
) -> None:
    now = _utc_now()
    conn.execute(
        """
        insert into replays (
          id, game_id, path, event_count, first_turn, last_turn, imported_at, metadata_json
        )
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            replay_id,
            game_id,
            path,
            event_count,
            first_turn,
            last_turn,
            now,
            json.dumps(metadata),
        ),
    )
    conn.commit()


def new_checkpoint_id() -> str:
    return f"ckpt_{uuid.uuid4().hex[:12]}"


def new_artifact_id() -> str:
    return f"art_{uuid.uuid4().hex[:12]}"


def new_metric_id() -> str:
    return f"ms_{uuid.uuid4().hex[:12]}"


@dataclass(slots=True)
class GameRow:
    id: str
    source: str
    job_id: str | None
    player_count: int
    seed: int | None
    strategy_specs_json: str
    status: str
    winner_id: str | None
    ended_by: str | None
    turn_count: int
    replay_path: str | None
    action_log_json: str | None
    created_at: str
    finished_at: str | None

    def strategy_specs(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.strategy_specs_json))

    def to_list_item(self) -> dict[str, Any]:
        return {
            "game_id": self.id,
            "source": self.source,
            "job_id": self.job_id,
            "player_count": self.player_count,
            "seed": self.seed,
            "status": self.status,
            "winner_id": self.winner_id,
            "turn_count": self.turn_count,
            "replay_path": self.replay_path,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "links": {"self": f"/api/games/{self.id}"},
        }

    def to_detail(self) -> dict[str, Any]:
        d = self.to_list_item()
        d["strategy_specs"] = self.strategy_specs()
        d["action_log"] = (
            cast(Any, json.loads(self.action_log_json))
            if self.action_log_json
            else None
        )
        return d


@dataclass(slots=True)
class ReplayRow:
    id: str
    game_id: str
    path: str
    event_count: int
    first_turn: int | None
    last_turn: int | None
    imported_at: str
    metadata_json: str

    def metadata(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.metadata_json))

    def to_list_item(self) -> dict[str, Any]:
        return {
            "replay_id": self.id,
            "game_id": self.game_id,
            "path": self.path,
            "event_count": self.event_count,
            "imported_at": self.imported_at,
            "metadata": self.metadata(),
            "links": {"self": f"/api/replays/{self.id}"},
        }

    def to_detail(self) -> dict[str, Any]:
        d = self.to_list_item()
        d["first_turn"] = self.first_turn
        d["last_turn"] = self.last_turn
        return d


@dataclass(slots=True)
class CheckpointRow:
    id: str
    path: str
    label: str | None
    player_count: int | None
    source_job_id: str | None
    schema_version: str | None
    strategy_spec: str
    training_stats_json: str
    manifest_path: str | None
    promoted: bool
    created_at: str

    def training_stats(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.training_stats_json))

    def to_list_item(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "label": self.label,
            "player_count": self.player_count,
            "strategy_spec": self.strategy_spec,
            "promoted": self.promoted,
            "created_at": self.created_at,
            "links": {"self": f"/api/checkpoints/{self.id}"},
        }

    def to_detail(self) -> dict[str, Any]:
        d = self.to_list_item()
        d["source_job_id"] = self.source_job_id
        d["schema_version"] = self.schema_version
        d["training_stats"] = self.training_stats()
        d["manifest_path"] = self.manifest_path
        return d


@dataclass(slots=True)
class EvaluationRow:
    id: str
    job_id: str | None
    candidate_spec: str
    player_count: int
    baselines_json: str
    games: int
    seed: int
    report_json: str
    candidate_score: float
    strategy_scores_json: str
    promoted: bool | None
    promotion_reason: str | None
    created_at: str

    def baselines(self) -> list[str]:
        return cast(list[str], json.loads(self.baselines_json))

    def strategy_scores(self) -> dict[str, float]:
        return cast(dict[str, float], json.loads(self.strategy_scores_json))

    def to_list_item(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "candidate": self.candidate_spec,
            "player_count": self.player_count,
            "games": self.games,
            "candidate_score": self.candidate_score,
            "promoted": self.promoted,
            "created_at": self.created_at,
            "links": {"self": f"/api/evaluations/{self.id}"},
        }

    def to_detail(self) -> dict[str, Any]:
        d = self.to_list_item()
        d["baselines"] = self.baselines()
        d["seed"] = self.seed
        d["report"] = cast(dict[str, Any], json.loads(self.report_json))
        d["strategy_scores"] = self.strategy_scores()
        d["promotion_reason"] = self.promotion_reason
        return d


@dataclass(slots=True)
class ArtifactRow:
    id: str
    kind: str
    rel_path: str
    label: str | None
    job_id: str | None
    checkpoint_id: str | None
    metadata_json: str
    created_at: str
    imported_at: str | None

    def metadata(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.metadata_json))

    def to_list_item(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "path": self.rel_path,
            "label": self.label,
            "metadata": self.metadata(),
            "created_at": self.created_at,
            "imported_at": self.imported_at,
            "links": {
                "self": f"/api/artifacts/{self.id}",
                "download": f"/api/artifacts/{self.id}/download",
            },
        }

    def to_detail(self) -> dict[str, Any]:
        d = self.to_list_item()
        d["job_id"] = self.job_id
        d["checkpoint_id"] = self.checkpoint_id
        return d


def _row_game(row: sqlite3.Row) -> GameRow:
    return GameRow(
        id=row["id"],
        source=row["source"],
        job_id=row["job_id"],
        player_count=row["player_count"],
        seed=row["seed"],
        strategy_specs_json=row["strategy_specs_json"],
        status=row["status"],
        winner_id=row["winner_id"],
        ended_by=row["ended_by"],
        turn_count=row["turn_count"],
        replay_path=row["replay_path"],
        action_log_json=row["action_log_json"],
        created_at=row["created_at"],
        finished_at=row["finished_at"],
    )


def _row_replay(row: sqlite3.Row) -> ReplayRow:
    return ReplayRow(
        id=row["id"],
        game_id=row["game_id"],
        path=row["path"],
        event_count=row["event_count"],
        first_turn=row["first_turn"],
        last_turn=row["last_turn"],
        imported_at=row["imported_at"],
        metadata_json=row["metadata_json"],
    )


def _row_checkpoint(row: sqlite3.Row) -> CheckpointRow:
    return CheckpointRow(
        id=row["id"],
        path=row["path"],
        label=row["label"],
        player_count=row["player_count"],
        source_job_id=row["source_job_id"],
        schema_version=row["schema_version"],
        strategy_spec=row["strategy_spec"],
        training_stats_json=row["training_stats_json"],
        manifest_path=row["manifest_path"],
        promoted=bool(row["promoted"]),
        created_at=row["created_at"],
    )


def _row_eval(row: sqlite3.Row) -> EvaluationRow:
    return EvaluationRow(
        id=row["id"],
        job_id=row["job_id"],
        candidate_spec=row["candidate_spec"],
        player_count=row["player_count"],
        baselines_json=row["baselines_json"],
        games=row["games"],
        seed=row["seed"],
        report_json=row["report_json"],
        candidate_score=row["candidate_score"],
        strategy_scores_json=row["strategy_scores_json"],
        promoted=(
            bool(row["promoted"]) if row["promoted"] is not None else None
        ),
        promotion_reason=row["promotion_reason"],
        created_at=row["created_at"],
    )


def _row_artifact(row: sqlite3.Row) -> ArtifactRow:
    return ArtifactRow(
        id=row["id"],
        kind=row["kind"],
        rel_path=row["rel_path"],
        label=row["label"],
        job_id=row["job_id"],
        checkpoint_id=row["checkpoint_id"],
        metadata_json=row["metadata_json"],
        created_at=row["created_at"],
        imported_at=row["imported_at"],
    )


def get_game(conn: sqlite3.Connection, game_id: str) -> GameRow | None:
    row = conn.execute("select * from games where id = ?", (game_id,)).fetchone()
    if row is None:
        return None
    return _row_game(row)


def list_games(
    conn: sqlite3.Connection,
    *,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
) -> Iterator[GameRow]:
    where: list[str] = []
    args: list[Any] = []
    if status is not None:
        where.append("status = ?")
        args.append(status)
    q = "select * from games"
    if where:
        allowed = {"status = ?"}
        for w in where:
            if w not in allowed:
                raise ValueError(f"Forbidden where clause: {w}")
        q += " where " + " and ".join(where)
    q += " order by created_at desc limit ? offset ?"
    args.extend([limit, offset])
    for row in conn.execute(q, args):
        yield _row_game(row)


def get_replay(conn: sqlite3.Connection, replay_id: str) -> ReplayRow | None:
    row = conn.execute("select * from replays where id = ?", (replay_id,)).fetchone()
    if row is None:
        return None
    return _row_replay(row)


def list_replays(
    conn: sqlite3.Connection,
    *,
    limit: int = 50,
    offset: int = 0,
) -> Iterator[ReplayRow]:
    for row in conn.execute(
        "select * from replays order by imported_at desc limit ? offset ?",
        (limit, offset),
    ):
        yield _row_replay(row)


def get_checkpoint(
    conn: sqlite3.Connection, checkpoint_id: str
) -> CheckpointRow | None:
    row = conn.execute(
        "select * from checkpoints where id = ?",
        (checkpoint_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_checkpoint(row)


def get_checkpoint_by_path(
    conn: sqlite3.Connection, rel_path: str
) -> CheckpointRow | None:
    row = conn.execute("select * from checkpoints where path = ?", (rel_path,)).fetchone()
    if row is None:
        return None
    return _row_checkpoint(row)


def list_checkpoints(
    conn: sqlite3.Connection,
    *,
    limit: int = 50,
    offset: int = 0,
    player_count: int | None = None,
) -> Iterator[CheckpointRow]:
    where: list[str] = []
    args: list[Any] = []
    if player_count is not None:
        where.append("player_count = ?")
        args.append(player_count)
    q = "select * from checkpoints"
    if where:
        allowed = {"player_count = ?"}
        for w in where:
            if w not in allowed:
                raise ValueError(f"Forbidden where clause: {w}")
        q += " where " + " and ".join(where)
    q += " order by created_at desc limit ? offset ?"
    args.extend([limit, offset])
    for row in conn.execute(q, args):
        yield _row_checkpoint(row)


def list_champions(conn: sqlite3.Connection) -> Iterator[CheckpointRow]:
    for row in conn.execute(
        "select * from checkpoints where promoted = 1 order by created_at desc"
    ):
        yield _row_checkpoint(row)


def get_evaluation(conn: sqlite3.Connection, eval_id: str) -> EvaluationRow | None:
    row = conn.execute("select * from evaluations where id = ?", (eval_id,)).fetchone()
    if row is None:
        return None
    return _row_eval(row)


def list_evaluations(
    conn: sqlite3.Connection, *, limit: int = 50, offset: int = 0
) -> Iterator[EvaluationRow]:
    for row in conn.execute(
        "select * from evaluations order by created_at desc limit ? offset ?",
        (limit, offset),
    ):
        yield _row_eval(row)


def get_artifact(conn: sqlite3.Connection, artifact_id: str) -> ArtifactRow | None:
    row = conn.execute("select * from artifacts where id = ?", (artifact_id,)).fetchone()
    if row is None:
        return None
    return _row_artifact(row)


def list_artifacts(
    conn: sqlite3.Connection,
    *,
    limit: int = 50,
    offset: int = 0,
    kind: str | None = None,
) -> Iterator[ArtifactRow]:
    where: list[str] = []
    args: list[Any] = []
    if kind is not None:
        where.append("kind = ?")
        args.append(kind)
    q = "select * from artifacts"
    if where:
        allowed = {"kind = ?"}
        for w in where:
            if w not in allowed:
                raise ValueError(f"Forbidden where clause: {w}")
        q += " where " + " and ".join(where)
    q += " order by created_at desc limit ? offset ?"
    args.extend([limit, offset])
    for row in conn.execute(q, args):
        yield _row_artifact(row)


def insert_checkpoint(
    conn: sqlite3.Connection,
    *,
    checkpoint_id: str,
    path: str,
    label: str | None,
    player_count: int | None,
    source_job_id: str | None,
    schema_version: str | None,
    strategy_spec: str,
    training_stats: dict[str, Any],
    manifest_path: str | None,
    promoted: bool = False,
) -> None:
    now = _utc_now()
    conn.execute(
        """
        insert into checkpoints (
          id, path, label, player_count, source_job_id, schema_version,
          strategy_spec, training_stats_json, manifest_path, promoted, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            checkpoint_id,
            path,
            label,
            player_count,
            source_job_id,
            schema_version,
            strategy_spec,
            json.dumps(training_stats),
            manifest_path,
            1 if promoted else 0,
            now,
        ),
    )
    conn.commit()


def set_checkpoint_promoted(
    conn: sqlite3.Connection, checkpoint_id: str, *, promoted: bool
) -> None:
    conn.execute(
        "update checkpoints set promoted = ? where id = ?",
        (1 if promoted else 0, checkpoint_id),
    )
    conn.commit()


def insert_evaluation(
    conn: sqlite3.Connection,
    *,
    evaluation_id: str,
    job_id: str | None,
    candidate_spec: str,
    player_count: int,
    baselines: list[str],
    games: int,
    seed: int,
    report: dict[str, Any],
    candidate_score: float,
    strategy_scores: dict[str, float],
    promoted: bool | None,
    promotion_reason: str | None,
) -> None:
    now = _utc_now()
    conn.execute(
        """
        insert into evaluations (
          id, job_id, candidate_spec, player_count, baselines_json, games, seed,
          report_json, candidate_score, strategy_scores_json, promoted,
          promotion_reason, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evaluation_id,
            job_id,
            candidate_spec,
            player_count,
            json.dumps(baselines),
            games,
            seed,
            json.dumps(report),
            candidate_score,
            json.dumps(strategy_scores),
            1 if promoted is True else (0 if promoted is False else None),
            promotion_reason,
            now,
        ),
    )
    conn.commit()


def insert_artifact(
    conn: sqlite3.Connection,
    *,
    artifact_id: str,
    kind: str,
    rel_path: str,
    label: str | None,
    job_id: str | None,
    checkpoint_id: str | None,
    metadata: dict[str, Any],
    imported_at: str | None = None,
) -> None:
    now = _utc_now()
    conn.execute(
        """
        insert into artifacts (
          id, kind, rel_path, label, job_id, checkpoint_id,
          metadata_json, created_at, imported_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact_id,
            kind,
            rel_path,
            label,
            job_id,
            checkpoint_id,
            json.dumps(metadata),
            now,
            imported_at,
        ),
    )
    conn.commit()


def insert_metric_summary(
    conn: sqlite3.Connection,
    *,
    metric_id: str,
    subject_type: str,
    subject_id: str,
    name: str,
    value: float,
    unit: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    now = _utc_now()
    conn.execute(
        """
        insert into metric_summaries (
          id, subject_type, subject_id, name, value, unit, metadata_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metric_id,
            subject_type,
            subject_id,
            name,
            value,
            unit,
            json.dumps(metadata or {}),
            now,
        ),
    )
    conn.commit()

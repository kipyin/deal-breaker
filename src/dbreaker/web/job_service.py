from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dbreaker.experiments.rl_search import (
    EvaluationConfig,
    evaluate_candidate,
    promote_champion,
    run_rl_search,
)
from dbreaker.experiments.tournament import run_tournament
from dbreaker.ml.trainer import train_self_play
from dbreaker.web import artifact_service
from dbreaker.web import db as db_mod
from dbreaker.web import training_service as tr
from dbreaker.web.config import WebConfig
from dbreaker.web.evaluation_service import (
    evaluation_result_to_dict,
    tournament_report_to_dict,
)
from dbreaker.web.schemas import (
    ArtifactImportJobRequest,
    RlSearchJobRequest,
    TournamentJobRequest,
    TrainingJobRequest,
)

EvaluateFn = Callable[..., Any]
TrainFn = Callable[..., Any]
RLSearchFn = Callable[..., list[Any]]
TournamentFn = Callable[..., Any]


def _to_rel(artifact_root: Path, p: str | Path) -> str:
    path = Path(p).resolve()
    return str(path.relative_to(artifact_root.resolve()))


class JobService:
    """In-process queue + worker thread for long-running web jobs."""

    def __init__(
        self,
        config: WebConfig,
        conn: sqlite3.Connection,
        *,
        evaluate_fn: EvaluateFn = evaluate_candidate,
        train_fn: TrainFn = train_self_play,
        rl_search_fn: RLSearchFn = run_rl_search,
        tournament_fn: TournamentFn = run_tournament,
    ) -> None:
        self._config = config
        self._conn = conn
        self._evaluate_fn = evaluate_fn
        self._train_fn = train_fn
        self._rl_search_fn = rl_search_fn
        self._tournament_fn = tournament_fn
        self._queue: deque[str] = deque()
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._run, name="dbreaker-jobs", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        self._worker.join(timeout=5.0)

    def _new_job(
        self, kind: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        rel_log = f"jobs/{job_id}/log.txt"
        log_path = self._config.artifact_root / rel_log
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("", encoding="utf-8")
        db_mod.insert_job(
            self._conn,
            job_id=job_id,
            kind=kind,
            config=config,
            log_path=rel_log,
        )
        with self._cond:
            self._queue.append(job_id)
            self._cond.notify()
        return {
            "job_id": job_id,
            "status": "queued",
            "links": {
                "self": f"/api/jobs/{job_id}",
                "logs": f"/api/jobs/{job_id}/logs",
            },
        }

    def enqueue_training(self, body: TrainingJobRequest) -> dict[str, Any]:
        return self._new_job("training", body.model_dump())

    def enqueue_rl_search(self, body: RlSearchJobRequest) -> dict[str, Any]:
        return self._new_job("rl_search", body.model_dump())

    def enqueue_evaluation(
        self,
        *,
        candidate: str,
        player_count: int,
        baselines: tuple[str, ...],
        games: int,
        seed: int,
        max_turns: int,
        max_self_play_steps: int,
        champions_manifest_path: str | None,
        promote_if_passes: bool = False,
        max_aborted_rate: float = 0.0,
    ) -> dict[str, Any]:
        cfg: dict[str, Any] = {
            "candidate": candidate,
            "player_count": player_count,
            "baselines": list(baselines),
            "games": games,
            "seed": seed,
            "max_turns": max_turns,
            "max_self_play_steps": max_self_play_steps,
            "champions_manifest_path": champions_manifest_path,
            "promote_if_passes": promote_if_passes,
            "max_aborted_rate": max_aborted_rate,
        }
        return self._new_job("evaluation", cfg)

    def enqueue_tournament(self, body: TournamentJobRequest) -> dict[str, Any]:
        return self._new_job("tournament", body.model_dump())

    def enqueue_artifact_import(self, body: ArtifactImportJobRequest) -> dict[str, Any]:
        return self._new_job("artifact_import", body.model_dump())

    def get_job(self, job_id: str) -> db_mod.JobRow | None:
        return db_mod.get_job(self._conn, job_id)

    def list_jobs(
        self,
        limit: int = 20,
        offset: int = 0,
        kind: str | None = None,
        status: str | None = None,
    ) -> list[db_mod.JobRow]:
        return list(
            db_mod.list_jobs(
                self._conn,
                limit=limit,
                offset=offset,
                kind=kind,
                status=status,
            )
        )

    def read_log(self, job_id: str, *, offset: int, limit: int) -> dict[str, Any] | None:
        row = db_mod.get_job(self._conn, job_id)
        if row is None or not row.log_path:
            return None
        path = self._config.artifact_root / row.log_path
        if not path.is_file():
            return {"lines": [], "offset": offset, "end_offset": offset}
        data = path.read_bytes()
        if offset < 0 or offset > len(data):
            offset = 0
        rest = data[offset:]
        text = rest.decode("utf-8", errors="replace")
        lines = text.splitlines()[:limit]
        next_off = offset
        for line in lines:
            next_off += len(line.encode("utf-8")) + 1
        return {
            "lines": lines,
            "offset": offset,
            "end_offset": min(next_off, len(data)),
        }

    @staticmethod
    def _log_rel(row: db_mod.JobRow) -> str:
        assert row.log_path is not None
        return row.log_path

    def _append_log(self, rel_path: str, message: str) -> None:
        path = self._config.artifact_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(message)
            if not message.endswith("\n"):
                f.write("\n")

    def _resolve_champion_path(self, champion_checkpoint_id: str | None) -> Path | None:
        if not champion_checkpoint_id:
            return None
        row = db_mod.get_checkpoint(self._conn, champion_checkpoint_id)
        if row is None:
            raise ValueError(f"unknown checkpoint: {champion_checkpoint_id}")
        p = self._config.artifact_root / row.path
        if not p.is_file():
            raise ValueError(f"checkpoint file missing: {p}")
        return p

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._cond:
                while not self._queue and not self._stop.is_set():
                    self._cond.wait(timeout=0.5)
                if self._stop.is_set() and not self._queue:
                    return
                if not self._queue:
                    continue
                job_id = self._queue.popleft()
            self._process_job(job_id)

    def _process_job(self, job_id: str) -> None:
        row = db_mod.get_job(self._conn, job_id)
        if row is None or row.log_path is None:
            return
        db_mod.update_job_status(self._conn, job_id, status="running")
        self._append_log(self._log_rel(row), "started")
        try:
            self._append_log(self._log_rel(row), f"config: {row.config_json}")
            if row.kind == "evaluation":
                self._run_evaluation_job(job_id, row)
            elif row.kind == "training":
                self._run_training_job(job_id, row)
            elif row.kind == "rl_search":
                self._run_rl_search_job(job_id, row)
            elif row.kind == "tournament":
                self._run_tournament_job(job_id, row)
            elif row.kind == "artifact_import":
                self._run_artifact_import_job(job_id, row)
            else:
                raise ValueError(f"unsupported job kind: {row.kind}")
        except Exception as exc:
            self._append_log(self._log_rel(row), f"error: {exc!r}")
            db_mod.update_job_status(
                self._conn, job_id, status="failed", error=str(exc)
            )

    def _run_training_job(self, job_id: str, row: db_mod.JobRow) -> None:
        cfg = TrainingJobRequest.model_validate_json(row.config_json)
        ch = self._resolve_champion_path(cfg.champion_checkpoint_id)
        ppo = tr.ppo_config_from_request(cfg, ch)
        ckpt_id, rel_pt, rel_json = tr.training_artifact_ids(
            job_id, cfg.player_count, cfg.checkpoint_label
        )
        out_pt = self._config.artifact_root / rel_pt
        out_pt.parent.mkdir(parents=True, exist_ok=True)
        stats = self._train_fn(ppo, checkpoint_out=out_pt, seed=cfg.seed)
        training = stats.as_dict()
        tr.write_training_manifest(rel_json, self._config.artifact_root, training)
        spec = f"neural:{rel_pt}"
        strategy_spec = spec
        artifact_service.index_checkpoint_path(
            self._conn,
            rel_path=rel_pt,
            job_id=job_id,
            label=cfg.checkpoint_label,
            strategy_spec=strategy_spec,
            training_stats=training,
            manifest_path=rel_json,
            checkpoint_id=ckpt_id,
        )
        rdict: dict[str, Any] = {
            "checkpoint_id": ckpt_id,
            "rel_checkpoint": rel_pt,
            "rel_manifest": rel_json,
            "training": training,
        }
        res_rel = f"jobs/{job_id}/result.json"
        (self._config.artifact_root / res_rel).parent.mkdir(parents=True, exist_ok=True)
        (self._config.artifact_root / res_rel).write_text(
            json.dumps(rdict, indent=2), encoding="utf-8"
        )
        self._append_log(self._log_rel(row), f"result written to {res_rel}")
        db_mod.update_job_status(self._conn, job_id, status="succeeded", result=rdict)
        self._append_log(self._log_rel(row), "finished")

    def _run_rl_search_job(self, job_id: str, row: db_mod.JobRow) -> None:
        cfg = RlSearchJobRequest.model_validate_json(row.config_json)
        ch = self._resolve_champion_path(cfg.champion_checkpoint_id)
        out_dir = self._config.artifact_root / "checkpoints" / "rl-search"
        out_dir.mkdir(parents=True, exist_ok=True)
        rc = tr.rl_search_config(
            cfg, output_dir=out_dir, champion_checkpoint=ch
        )
        manifests = self._rl_search_fn(rc)
        indexed: list[str] = []
        for m in manifests:
            rel_ckpt = _to_rel(self._config.artifact_root, m.checkpoint_path)
            man_rel: str | None
            if Path(m.manifest_path).is_file():
                man_rel = _to_rel(self._config.artifact_root, m.manifest_path)
            else:
                man_rel = None
            ts = m.training
            st = {k: v for k, v in ts.items() if v is not None} if ts else {}
            aid = artifact_service.index_checkpoint_path(
                self._conn,
                rel_path=rel_ckpt,
                job_id=job_id,
                label=Path(m.checkpoint_path).stem,
                strategy_spec=f"neural:{rel_ckpt}",
                training_stats=st,
                manifest_path=man_rel,
            )
            indexed.append(aid)
        rdict: dict[str, Any] = {
            "manifests": [m.as_dict() for m in manifests],
            "checkpoint_ids": indexed,
        }
        res_rel = f"jobs/{job_id}/result.json"
        (self._config.artifact_root / res_rel).parent.mkdir(parents=True, exist_ok=True)
        (self._config.artifact_root / res_rel).write_text(
            json.dumps(rdict, default=str, indent=2), encoding="utf-8"
        )
        self._append_log(self._log_rel(row), f"result written to {res_rel}")
        db_mod.update_job_status(self._conn, job_id, status="succeeded", result=rdict)
        self._append_log(self._log_rel(row), "finished")

    def _run_tournament_job(self, job_id: str, row: db_mod.JobRow) -> None:
        data = json.loads(row.config_json)
        body = TournamentJobRequest.model_validate(data)
        report = self._tournament_fn(
            player_count=body.player_count,
            games=body.games,
            strategy_names=body.strategies,
            seed=body.seed,
            max_turns=body.max_turns,
            max_self_play_steps=body.max_self_play_steps,
        )
        rpt = tournament_report_to_dict(report)
        res_rel = f"jobs/{job_id}/tournament.json"
        out = self._config.artifact_root / res_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rpt, indent=2), encoding="utf-8")
        rdict: dict[str, Any] = {"report": rpt, "result_path": res_rel}
        art_id = db_mod.new_artifact_id()
        db_mod.insert_artifact(
            self._conn,
            artifact_id=art_id,
            kind="tournament_report",
            rel_path=res_rel,
            label=job_id,
            job_id=job_id,
            checkpoint_id=None,
            metadata={"tournament": True, "strategies": body.strategies},
        )
        db_mod.update_job_status(self._conn, job_id, status="succeeded", result=rdict)
        self._append_log(self._log_rel(row), f"tournament report at {res_rel}")
        self._append_log(self._log_rel(row), "finished")

    def _run_artifact_import_job(self, job_id: str, row: db_mod.JobRow) -> None:
        body = ArtifactImportJobRequest.model_validate_json(row.config_json)
        ids = artifact_service.import_rl_search_tree(
            self._config, self._conn, body.rel_path
        )
        rdict: dict[str, Any] = {
            "imported_checkpoint_ids": ids,
            "count": len(ids),
            "rel_path": body.rel_path,
        }
        db_mod.update_job_status(self._conn, job_id, status="succeeded", result=rdict)
        self._append_log(
            self._log_rel(row),
            f"imported {len(ids)} checkpoint(s) from {body.rel_path}",
        )
        self._append_log(self._log_rel(row), "finished")

    def _run_evaluation_job(self, job_id: str, row: db_mod.JobRow) -> None:
        cfg = json.loads(row.config_json)
        ch = cfg.get("champions_manifest_path")
        ch_path: Path | None
        if ch is None:
            ch_path = None
        else:
            p = Path(ch)
            ch_path = p if p.is_absolute() else (self._config.artifact_root / p)
        eval_config = EvaluationConfig(
            player_count=cfg["player_count"],
            candidate=cfg["candidate"],
            baselines=tuple(cfg.get("baselines", ("basic",))),
            games=cfg["games"],
            seed=cfg["seed"],
            max_turns=cfg["max_turns"],
            max_self_play_steps=cfg["max_self_play_steps"],
            champions_path=ch_path,
        )
        result = self._evaluate_fn(eval_config)
        rdict = evaluation_result_to_dict(result)
        promote_if = bool(cfg.get("promote_if_passes"))
        max_aborted = float(cfg.get("max_aborted_rate", 0.0))
        promoted: bool | None = None
        prom_reason: str | None = None
        cspec = str(cfg["candidate"])
        if (
            promote_if
            and ch_path is not None
            and cspec.startswith("neural:")
        ):
            ckpt_arg = cspec[7:].lstrip()
            cpath = str(
                self._config.artifact_root / ckpt_arg
                if not Path(ckpt_arg).is_absolute()
                else Path(ckpt_arg)
            )
            dec = promote_champion(
                ch_path,
                result,
                checkpoint_path=cpath,
                max_aborted_rate=max_aborted,
            )
            rdict["promotion"] = {
                "promoted": dec.promoted,
                "reason": dec.reason,
            }
            promoted = dec.promoted
            prom_reason = dec.reason
            if dec.promoted:
                try:
                    rel_candidate = _to_rel(self._config.artifact_root, Path(cpath))
                except ValueError:
                    rel_candidate = ckpt_arg
                cprow = db_mod.get_checkpoint_by_path(self._conn, rel_candidate)
                if cprow is not None:
                    db_mod.set_checkpoint_promoted(
                        self._conn, cprow.id, promoted=True
                    )
        res_rel = f"jobs/{job_id}/result.json"
        out = self._config.artifact_root / res_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rdict, indent=2), encoding="utf-8")
        self._append_log(self._log_rel(row), f"result written to {res_rel}")
        db_mod.update_job_status(
            self._conn, job_id, status="succeeded", result=rdict
        )
        ev_rel = f"evaluations/{job_id}/report.json"
        evp = self._config.artifact_root / ev_rel
        evp.parent.mkdir(parents=True, exist_ok=True)
        evp.write_text(json.dumps(rdict, indent=2), encoding="utf-8")
        ar_id = db_mod.new_artifact_id()
        db_mod.insert_artifact(
            self._conn,
            artifact_id=ar_id,
            kind="evaluation_report",
            rel_path=ev_rel,
            label=job_id,
            job_id=job_id,
            checkpoint_id=None,
            metadata={"job_id": job_id, "candidate": cfg["candidate"]},
        )
        self._insert_evaluation_record(
            job_id=job_id,
            cfg=cfg,
            rdict=rdict,
            promoted=promoted,
            promotion_reason=prom_reason,
        )
        self._append_log(self._log_rel(row), "finished")

    def _insert_evaluation_record(
        self,
        *,
        job_id: str,
        cfg: dict[str, Any],
        rdict: dict[str, Any],
        promoted: bool | None,
        promotion_reason: str | None,
    ) -> None:
        report = {
            "summary": {k: rdict[k] for k in rdict if k != "report"},
            "tournament": rdict.get("report"),
        }
        db_mod.insert_evaluation(
            self._conn,
            evaluation_id=job_id,
            job_id=job_id,
            candidate_spec=cfg["candidate"],
            player_count=cfg["player_count"],
            baselines=list(cfg.get("baselines", [])),
            games=cfg["games"],
            seed=cfg["seed"],
            report=report,
            candidate_score=float(rdict["candidate_score"]),
            strategy_scores={k: float(v) for k, v in rdict["strategy_scores"].items()},
            promoted=promoted,
            promotion_reason=promotion_reason,
        )
        for name, val in [
            ("candidate_score", rdict["candidate_score"]),
            ("aborted_rate", rdict["aborted_rate"]),
            ("stalemate_rate", rdict["stalemate_rate"]),
            ("max_turn_rate", rdict["max_turn_rate"]),
        ]:
            db_mod.insert_metric_summary(
                self._conn,
                metric_id=db_mod.new_metric_id(),
                subject_type="evaluation",
                subject_id=job_id,
                name=name,
                value=float(val),
            )

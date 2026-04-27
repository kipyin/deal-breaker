from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from dbreaker.engine.actions import action_from_payload
from dbreaker.web import db as db_mod
from dbreaker.web import replay_service, strategy_service
from dbreaker.web.config import WebConfig
from dbreaker.web.game_service import GameService
from dbreaker.web.job_service import JobService
from dbreaker.web.schemas import (
    AiStepRequest,
    ArtifactImportJobRequest,
    EvalJobRequest,
    GameActionRequest,
    NewGameRequest,
    RlSearchJobRequest,
    TournamentJobRequest,
    TrainingJobRequest,
)


def create_app(
    data_root: Path,
    artifact_root: Path,
    *,
    cors_origin: str = "http://127.0.0.1:5173",
) -> FastAPI:
    config = WebConfig(data_root=data_root, artifact_root=artifact_root)
    config.ensure_dirs()
    conn = db_mod.connect(config.sqlite_path)
    db_mod.init_schema(conn)
    game_svc = GameService(config, conn)
    job_svc = JobService(config, conn)

    @asynccontextmanager
    async def lifespan(app2: FastAPI) -> AsyncIterator[None]:
        yield
        app2.state.jobs.stop()
        app2.state.conn.close()

    app = FastAPI(title="dbreaker web", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[cors_origin, "http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.config = config
    app.state.conn = conn
    app.state.games = game_svc
    app.state.jobs = job_svc

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "service": "dbreaker",
            "api_health": "/api/health",
            "ui": (
                "Start the Vite app from the web/ directory; it defaults to "
                "http://127.0.0.1:5173 and talks to this API."
            ),
        }

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/games", status_code=201)
    def post_game(payload: NewGameRequest) -> dict[str, Any]:
        try:
            return cast(
                dict[str, Any],
                app.state.games.new_session(
                    player_count=payload.player_count,
                    human_player_id=payload.human_player_id,
                    ai_strategy=payload.ai_strategy,
                    seed=payload.seed,
                ),
            )
        except ValueError as e:
            raise HTTPException(400, detail=str(e)) from e

    @app.get("/api/games/{game_id}/inspector")
    def get_game_inspector(
        game_id: str, viewer: str = "P1", omniscient: bool = False
    ) -> dict[str, Any]:
        s = app.state.games.inspect(game_id, viewer=viewer)
        if s is None:
            raise HTTPException(404, detail="unknown game_id")
        return cast(dict[str, Any], s)

    @app.post("/api/games/{game_id}/actions")
    def post_action(game_id: str, body: GameActionRequest) -> dict[str, Any]:
        try:
            action = action_from_payload(body.action)
        except (KeyError, ValueError, TypeError) as e:
            raise HTTPException(400, detail=f"invalid action: {e}") from e
        r = app.state.games.apply_action(
            game_id,
            player_id=body.player_id,
            expected_version=body.expected_version,
            action=action,
        )
        if r is None:
            raise HTTPException(404, detail="unknown game_id")
        if "error" in r:
            code = 409 if r.get("error") == "stale" else 400
            if r.get("error") == "stale":
                raise HTTPException(
                    409, detail={"error": "stale_version", "version": r.get("version")}
                )
            raise HTTPException(code, detail=r)
        return cast(dict[str, Any], r)

    @app.post("/api/games/{game_id}/ai-step")
    def post_ai_step(game_id: str, body: AiStepRequest) -> dict[str, Any]:
        r = app.state.games.ai_step(
            game_id, expected_version=body.expected_version, max_steps=body.max_steps
        )
        if r is None:
            raise HTTPException(404, detail="unknown game_id")
        if "error" in r:
            raise HTTPException(409, detail={"error": "stale_version", "version": r.get("version")})
        return cast(dict[str, Any], r)

    @app.get("/api/replays/{replay_id}/inspector")
    def get_replay_inspector(
        replay_id: str, step: int = 0, viewer: str = "P1"
    ) -> dict[str, Any]:
        row = replay_service.get_replay_row(app.state.conn, replay_id)
        if row is None:
            raise HTTPException(404, detail="unknown replay_id")
        rel = row["path"]
        path = app.state.config.artifact_root / rel
        if not path.is_file():
            raise HTTPException(404, detail="replay file missing")
        payload = replay_service.load_replay_file(path)
        n = len(payload.get("action_log", []))
        if step < 0 or step > n:
            raise HTTPException(400, detail=f"step must be 0..{n}")
        try:
            n = len(payload.get("action_log", []))
            data = replay_service.inspector_for_replay(
                replay_id, payload, step=step, viewer=viewer
            )
            data["replay"] = {"replay_id": replay_id, "max_step": n, "step": step}
            return data
        except ValueError as e:
            raise HTTPException(400, detail=str(e)) from e

    @app.post("/api/jobs/evaluations", status_code=201)
    def post_eval(payload: EvalJobRequest) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            app.state.jobs.enqueue_evaluation(
                candidate=payload.candidate,
                player_count=payload.player_count,
                baselines=tuple(payload.baselines),
                games=payload.games,
                seed=payload.seed,
                max_turns=payload.max_turns,
                max_self_play_steps=payload.max_self_play_steps,
                champions_manifest_path=payload.champions_manifest_path,
                promote_if_passes=payload.promote_if_passes,
                max_aborted_rate=payload.max_aborted_rate,
            ),
        )

    @app.post("/api/jobs/training", status_code=201)
    def post_training(payload: TrainingJobRequest) -> dict[str, Any]:
        return cast(dict[str, Any], app.state.jobs.enqueue_training(payload))

    @app.post("/api/jobs/rl-search", status_code=201)
    def post_rl_search(payload: RlSearchJobRequest) -> dict[str, Any]:
        return cast(dict[str, Any], app.state.jobs.enqueue_rl_search(payload))

    @app.post("/api/jobs/tournament", status_code=201)
    def post_tournament(payload: TournamentJobRequest) -> dict[str, Any]:
        return cast(dict[str, Any], app.state.jobs.enqueue_tournament(payload))

    @app.post("/api/jobs/artifact-import", status_code=201)
    def post_artifact_import(payload: ArtifactImportJobRequest) -> dict[str, Any]:
        return cast(
            dict[str, Any], app.state.jobs.enqueue_artifact_import(payload)
        )

    @app.get("/api/strategies")
    def get_strategies() -> dict[str, Any]:
        return cast(dict[str, Any], strategy_service.list_strategies())

    @app.get("/api/games")
    def list_games(
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> dict[str, Any]:
        rows = list(
            db_mod.list_games(
                app.state.conn, limit=limit, offset=offset, status=status
            )
        )
        return {"items": [g.to_list_item() for g in rows]}

    @app.get("/api/games/{game_id}")
    def get_game_detail(game_id: str) -> dict[str, Any]:
        row = db_mod.get_game(app.state.conn, game_id)
        if row is None:
            raise HTTPException(404, detail="unknown game_id")
        return row.to_detail()

    @app.get("/api/replays")
    def list_replays_api(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        rows = list(
            db_mod.list_replays(app.state.conn, limit=limit, offset=offset)
        )
        return {"items": [r.to_list_item() for r in rows]}

    @app.get("/api/replays/{replay_id}")
    def get_replay_detail(replay_id: str) -> dict[str, Any]:
        row = db_mod.get_replay(app.state.conn, replay_id)
        if row is None:
            raise HTTPException(404, detail="unknown replay_id")
        return row.to_detail()

    @app.get("/api/jobs")
    def list_jobs(
        limit: int = 20,
        offset: int = 0,
        kind: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        rows = app.state.jobs.list_jobs(
            limit=limit, offset=offset, kind=kind, status=status
        )
        return {
            "items": [j.to_api_dict() for j in rows],
        }

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        row = app.state.jobs.get_job(job_id)
        if row is None:
            raise HTTPException(404, detail="unknown job_id")
        return cast(dict[str, Any], row.to_api_dict())

    @app.get("/api/jobs/{job_id}/logs")
    def get_logs(job_id: str, offset: int = 0, limit: int = 200) -> dict[str, Any]:
        r = app.state.jobs.read_log(job_id, offset=offset, limit=limit)
        if r is None:
            raise HTTPException(404, detail="unknown job_id")
        return cast(dict[str, Any], r)

    @app.get("/api/sessions/{game_id}/replay-link")
    def replay_link(game_id: str) -> dict[str, str | None]:
        session = app.state.games.get_session(game_id)
        if session is None:
            raise HTTPException(404, detail="unknown game_id")
        return {"replay_id": session.last_replay_id}

    @app.get("/api/checkpoints")
    def list_checkpoints(
        limit: int = 50,
        offset: int = 0,
        player_count: int | None = None,
    ) -> dict[str, Any]:
        rows = list(
            db_mod.list_checkpoints(
                app.state.conn,
                limit=limit,
                offset=offset,
                player_count=player_count,
            )
        )
        return {"items": [c.to_list_item() for c in rows]}

    @app.get("/api/checkpoints/{checkpoint_id}")
    def get_checkpoint_detail(checkpoint_id: str) -> dict[str, Any]:
        row = db_mod.get_checkpoint(app.state.conn, checkpoint_id)
        if row is None:
            raise HTTPException(404, detail="unknown checkpoint_id")
        return row.to_detail()

    @app.get("/api/evaluations")
    def list_evaluations_api(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        rows = list(
            db_mod.list_evaluations(
                app.state.conn, limit=limit, offset=offset
            )
        )
        return {"items": [e.to_list_item() for e in rows]}

    @app.get("/api/evaluations/{evaluation_id}")
    def get_evaluation_detail(evaluation_id: str) -> dict[str, Any]:
        row = db_mod.get_evaluation(app.state.conn, evaluation_id)
        if row is None:
            raise HTTPException(404, detail="unknown evaluation_id")
        return row.to_detail()

    @app.get("/api/artifacts")
    def list_artifacts_api(
        limit: int = 50,
        offset: int = 0,
        kind: str | None = None,
    ) -> dict[str, Any]:
        rows = list(
            db_mod.list_artifacts(
                app.state.conn, limit=limit, offset=offset, kind=kind
            )
        )
        return {"items": [a.to_list_item() for a in rows]}

    @app.get("/api/artifacts/{artifact_id}")
    def get_artifact_detail(artifact_id: str) -> dict[str, Any]:
        row = db_mod.get_artifact(app.state.conn, artifact_id)
        if row is None:
            raise HTTPException(404, detail="unknown artifact_id")
        return row.to_detail()

    @app.get("/api/artifacts/{artifact_id}/download")
    def download_artifact(artifact_id: str) -> FileResponse:
        row = db_mod.get_artifact(app.state.conn, artifact_id)
        if row is None:
            raise HTTPException(404, detail="unknown artifact_id")
        path = app.state.config.artifact_root / row.rel_path
        if not path.is_file():
            raise HTTPException(404, detail="artifact file missing")
        return FileResponse(
            path,
            filename=path.name,
            media_type="application/octet-stream",
        )

    @app.get("/api/champions")
    def list_champions() -> dict[str, Any]:
        rows = list(db_mod.list_champions(app.state.conn))
        return {"items": [c.to_list_item() for c in rows]}

    return app

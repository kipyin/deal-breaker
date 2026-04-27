"""Focused API contract tests: 404s, query params, and list filters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dbreaker.web import db as db_mod
from dbreaker.web.app import create_app


@pytest.fixture()
def web_client(tmp_path: Path) -> TestClient:
    data = tmp_path / "data"
    art = tmp_path / "artifacts"
    app = create_app(data_root=data, artifact_root=art)
    with TestClient(app) as client:
        yield client


def test_not_found_endpoints_return_404(web_client: TestClient) -> None:
    assert web_client.get("/api/games/no_such_id").status_code == 404
    assert web_client.get("/api/replays/no_such_id").status_code == 404
    assert web_client.get("/api/jobs/no_such_job").status_code == 404
    assert web_client.get("/api/jobs/no_such_job/logs").status_code == 404
    assert web_client.get("/api/checkpoints/no_such_ckpt").status_code == 404
    assert web_client.get("/api/evaluations/no_such_eval").status_code == 404
    assert web_client.get("/api/artifacts/no_such_artifact").status_code == 404
    assert web_client.get("/api/artifacts/no_such_artifact/download").status_code == 404


def test_replay_inspector_step_out_of_range(web_client: TestClient) -> None:
    from dbreaker.engine.game import Game

    g = Game.new(player_count=2, seed=1)
    for _ in range(3):
        if g.is_terminal():
            break
        p = g.active_player_id
        legal = g.legal_actions(p)
        if not legal:
            break
        g.step(p, legal[0])
    n = len(g.action_log)
    root = web_client.app.state.config.artifact_root
    rel = "replays/short.json"
    out = root / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    game_id = "game_short"
    out.write_text(
        json.dumps(
            {
                "version": 1,
                "format": "dbreaker-action-log",
                "game_id": game_id,
                "player_count": 2,
                "seed": 1,
                "action_log": g.action_log,
            }
        ),
        encoding="utf-8",
    )
    conn = web_client.app.state.conn
    db_mod.insert_game(
        conn,
        game_id=game_id,
        source="scripted",
        player_count=2,
        seed=1,
        strategy_specs={},
    )
    rid = "replay_short"
    db_mod.insert_replay(
        conn,
        replay_id=rid,
        game_id=game_id,
        path=rel,
        event_count=len(g.event_log),
        first_turn=0,
        last_turn=g.state.turn,
        metadata={},
    )
    bad = web_client.get(f"/api/replays/{rid}/inspector?step={n + 1}&viewer=P1")
    assert bad.status_code == 400
    detail = bad.json()["detail"]
    text = detail if isinstance(detail, str) else str(detail)
    assert "step" in text.lower() or "0.." in text


def test_game_detail_shape_after_create(web_client: TestClient) -> None:
    r = web_client.post(
        "/api/games",
        json={"player_count": 2, "human_player_id": "P1", "ai_strategy": "basic", "seed": 2},
    )
    assert r.status_code == 201
    gid = r.json()["game_id"]
    d = web_client.get(f"/api/games/{gid}").json()
    assert d["game_id"] == gid
    assert d["status"] in {"active", "completed", "aborted"}
    assert d["player_count"] == 2


def test_replay_list_contains_inserted(web_client: TestClient) -> None:
    from dbreaker.engine.game import Game

    g = Game.new(player_count=2, seed=5)
    if not g.is_terminal():
        p = g.active_player_id
        la = g.legal_actions(p)
        if la:
            g.step(p, la[0])
    root = web_client.app.state.config.artifact_root
    rel = "replays/list_test.jsonl"
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text("{}", encoding="utf-8")
    conn = web_client.app.state.conn
    game_id = "g_list"
    db_mod.insert_game(
        conn,
        game_id=game_id,
        source="imported",
        player_count=2,
        seed=5,
        strategy_specs={},
    )
    rid = "r_list_1"
    db_mod.insert_replay(
        conn,
        replay_id=rid,
        game_id=game_id,
        path=rel,
        event_count=0,
        first_turn=0,
        last_turn=0,
        metadata={},
    )
    items = web_client.get("/api/replays?limit=10").json()["items"]
    assert any(x.get("replay_id") == rid for x in items)


def test_jobs_list_accepts_filters(web_client: TestClient) -> None:
    r = web_client.get("/api/jobs?kind=evaluation&status=queued&limit=5")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)
    for item in body["items"]:
        assert item.get("kind") == "evaluation"


def test_artifact_download_serves_file(web_client: TestClient) -> None:
    root = web_client.app.state.config.artifact_root
    rel = "imports/hello.bin"
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"hello")
    conn = web_client.app.state.conn
    aid = "art_test_dl"
    db_mod.insert_artifact(
        conn,
        artifact_id=aid,
        kind="import",
        rel_path=rel,
        label=None,
        job_id=None,
        checkpoint_id=None,
        metadata={},
    )
    r = web_client.get(f"/api/artifacts/{aid}/download")
    assert r.status_code == 200
    assert r.content == b"hello"

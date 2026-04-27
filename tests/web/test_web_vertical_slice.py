from __future__ import annotations

import json
import time
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


def test_root(web_client: TestClient) -> None:
    r = web_client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "dbreaker"
    assert body["api_health"] == "/api/health"


def test_health(web_client: TestClient) -> None:
    r = web_client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_new_game_contract(web_client: TestClient) -> None:
    r = web_client.post(
        "/api/games",
        json={"player_count": 2, "human_player_id": "P1", "ai_strategy": "basic", "seed": 1},
    )
    assert r.status_code == 201
    body = r.json()
    assert "game_id" in body
    assert body["version"] == 0
    assert "inspector" in body
    assert body["inspector"]["game_id"] == body["game_id"]
    ins = body["inspector"]
    assert ins.get("deck_count", 0) >= 0
    assert ins.get("discard_count", 0) == 0
    assert ins.get("discard_top") is None


def test_game_action_step_engine(web_client: TestClient) -> None:
    r = web_client.post(
        "/api/games",
        json={"player_count": 2, "human_player_id": "P1", "ai_strategy": "basic", "seed": 7},
    )
    gid = r.json()["game_id"]
    r2 = web_client.get(f"/api/games/{gid}/inspector?viewer=P1")
    assert r2.status_code == 200
    ins = r2.json()
    assert ins["version"] == 0
    draw = next(
        (a for a in ins["legal_actions"] if a["payload"].get("type") == "DrawCards"),
        None,
    )
    assert draw is not None
    r3 = web_client.post(
        f"/api/games/{gid}/actions",
        json={
            "player_id": "P1",
            "expected_version": 0,
            "action": draw["payload"],
        },
    )
    assert r3.status_code == 200
    assert r3.json()["version"] >= 1


def test_stale_version_409(web_client: TestClient) -> None:
    r = web_client.post(
        "/api/games",
        json={"player_count": 2, "human_player_id": "P1", "ai_strategy": "basic"},
    )
    gid = r.json()["game_id"]
    ins = web_client.get(f"/api/games/{gid}/inspector?viewer=P1").json()
    d = next(
        a["payload"] for a in ins["legal_actions"] if a["payload"].get("type") == "DrawCards"
    )
    r2 = web_client.post(
        f"/api/games/{gid}/actions",
        json={"player_id": "P1", "expected_version": 0, "action": d},
    )
    assert r2.status_code == 200
    r3 = web_client.post(
        f"/api/games/{gid}/actions",
        json={"player_id": "P1", "expected_version": 0, "action": d},
    )
    assert r3.status_code == 409


def test_replay_inspector_steps_engine_round_trip(web_client: TestClient, tmp_path: Path) -> None:
    from dbreaker.engine.game import Game

    g = Game.new(player_count=2, seed=99)
    for _ in range(8):
        if g.is_terminal():
            break
        p = g.active_player_id
        legal = g.legal_actions(p)
        if not legal:
            break
        g.step(p, legal[0])

    rel = "replays/manual_test.json"
    out = tmp_path / "artifacts" / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    game_id = "game_manual"
    payload = {
        "version": 1,
        "format": "dbreaker-action-log",
        "game_id": game_id,
        "player_count": 2,
        "seed": 99,
        "action_log": g.action_log,
    }
    out.write_text(json.dumps(payload), encoding="utf-8")
    conn = web_client.app.state.conn
    db_mod.insert_game(
        conn,
        game_id=game_id,
        source="scripted",
        player_count=2,
        seed=99,
        strategy_specs={"note": "test"},
    )
    rid = "replay_manual"
    db_mod.insert_replay(
        conn,
        replay_id=rid,
        game_id=game_id,
        path=rel,
        event_count=len(g.event_log),
        first_turn=0,
        last_turn=g.state.turn,
        metadata={"test": True},
    )

    n = len(g.action_log)
    in0 = web_client.get(f"/api/replays/{rid}/inspector?step=0&viewer=P1")
    assert in0.status_code == 200
    ins0 = in0.json()
    assert ins0["replay"]["max_step"] == n
    assert "deck_count" in ins0 and isinstance(ins0["deck_count"], int)
    assert "discard_count" in ins0 and isinstance(ins0["discard_count"], int)
    assert ins0.get("discard_top") is None or isinstance(ins0.get("discard_top"), dict)
    inf = web_client.get(f"/api/replays/{rid}/inspector?step={n}&viewer=P1")
    assert inf.status_code == 200
    assert inf.json()["version"] == n


def test_strategies_and_list_endpoints(web_client: TestClient) -> None:
    r = web_client.get("/api/strategies")
    assert r.status_code == 200
    body = r.json()
    assert "built_in" in body
    assert "basic" in body["built_in"]
    assert web_client.get("/api/games").status_code == 200
    assert web_client.get("/api/replays").status_code == 200
    assert web_client.get("/api/jobs?kind=evaluation&limit=5").status_code == 200
    assert web_client.get("/api/checkpoints").status_code == 200
    assert web_client.get("/api/evaluations").status_code == 200
    assert web_client.get("/api/artifacts").status_code == 200
    assert web_client.get("/api/champions").status_code == 200


def test_eval_job_persistence(
    web_client: TestClient, tmp_path: Path
) -> None:
    r = web_client.post(
        "/api/jobs/evaluations",
        json={
            "candidate": "basic",
            "player_count": 2,
            "baselines": ["aggressive"],
            "games": 1,
            "seed": 1,
        },
    )
    assert r.status_code == 201
    job_id = r.json()["job_id"]
    db = tmp_path / "data" / "dbreaker.sqlite3"
    assert db.is_file()
    for _ in range(200):
        row = web_client.get(f"/api/jobs/{job_id}")
        assert row.status_code == 200
        st = row.json()["status"]
        if st in {"succeeded", "failed"}:
            break
        time.sleep(0.05)
    else:
        pytest.fail("job did not complete")
    final = web_client.get(f"/api/jobs/{job_id}").json()
    assert final["status"] == "succeeded"
    assert final["result"] is not None
    log = web_client.get(f"/api/jobs/{job_id}/logs")
    assert log.status_code == 200
    assert "lines" in log.json()

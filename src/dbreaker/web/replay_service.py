from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from dbreaker.engine.game import Game
from dbreaker.replay.player import Digest, ReplayRecord, replay_records
from dbreaker.web.inspector_service import build_inspector_state

_ACTION_LOG_KEY = "action_log"


def _digest_from_json(value: object) -> object:
    """JSON lists round-trip as lists; state digests are nested tuples of scalars and tuples."""
    if isinstance(value, list):
        return tuple(_digest_from_json(v) for v in value)
    return value


def _records_from_action_log(
    action_log: list[dict[str, Any]],
) -> list[ReplayRecord]:
    return [
        ReplayRecord(
            player_id=entry["player_id"],
            action_payload=entry["action_payload"],
            before_digest=cast(Digest, _digest_from_json(entry["before_digest"])),
            after_digest=cast(Digest, _digest_from_json(entry["after_digest"])),
            event_digests=tuple(
                cast(Digest, _digest_from_json(d)) for d in entry["event_digests"]
            ),
        )
        for entry in action_log
    ]


def load_replay_file(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def build_game_at_step(payload: dict[str, Any], step: int) -> Game:
    """Return engine Game replayed to ``step`` actions (0 = initial deal)."""
    player_count = int(payload["player_count"])
    raw_seed = payload.get("seed")
    seed: int | None = int(raw_seed) if raw_seed is not None else None
    action_log: list[dict[str, Any]] = payload.get(_ACTION_LOG_KEY, [])
    if step < 0 or step > len(action_log):
        raise ValueError("step out of range")
    records = _records_from_action_log(action_log[:step])
    if not records:
        return Game.new(player_count=player_count, seed=seed)
    seed_replay = 0 if seed is None else seed
    return replay_records(
        player_count=player_count, seed=seed_replay, records=records
    )


def inspector_for_replay(
    replay_id: str, payload: dict[str, Any], *, step: int, viewer: str
) -> dict[str, Any]:
    game_id = str(payload.get("game_id", replay_id))
    game = build_game_at_step(payload, step)
    return build_inspector_state(game, game_id=game_id, viewer=viewer)


def get_replay_row(conn: sqlite3.Connection, replay_id: str) -> sqlite3.Row | None:
    return cast(
        sqlite3.Row | None,
        conn.execute("select * from replays where id = ?", (replay_id,)).fetchone(),
    )

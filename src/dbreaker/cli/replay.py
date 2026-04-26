from __future__ import annotations

from pathlib import Path

from dbreaker.engine.events import GameEvent
from dbreaker.replay.log_store import read_events


def load_replay(path: Path) -> list[GameEvent]:
    return read_events(path)

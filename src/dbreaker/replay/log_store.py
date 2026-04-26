from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dbreaker.engine.events import GameEvent


def write_events(path: Path, events: list[GameEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(asdict(event), sort_keys=True) + "\n")


def read_events(path: Path) -> list[GameEvent]:
    events: list[GameEvent] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            data: dict[str, Any] = json.loads(line)
            events.append(GameEvent(**data))
    return events

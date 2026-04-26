from __future__ import annotations

from dbreaker.engine.events import GameEvent


def filter_events(
    events: list[GameEvent],
    *,
    player: str | None = None,
    event_type: str | None = None,
) -> list[GameEvent]:
    return [
        event
        for event in events
        if (player is None or event.player == player)
        and (event_type is None or event.type == event_type)
    ]

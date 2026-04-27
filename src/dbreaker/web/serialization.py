from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, cast

from dbreaker.engine.cards import Card, PropertyColor


def _json_default(obj: object) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def card_to_json(card: Card) -> dict[str, Any]:
    raw = json.dumps(asdict(card), default=_json_default)
    return cast(dict[str, Any], json.loads(raw))


def color_key(color: PropertyColor) -> str:
    return color.value


def property_table_json(table: dict[PropertyColor, list[Card]]) -> dict[str, list[dict[str, Any]]]:
    return {c.value: [card_to_json(x) for x in cards] for c, cards in table.items()}


def property_table_opp(
    table: dict[PropertyColor, tuple[Card, ...]],
) -> dict[str, list[dict[str, Any]]]:
    return {c.value: [card_to_json(x) for x in cards] for c, cards in table.items()}

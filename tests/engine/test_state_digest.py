from __future__ import annotations

from dbreaker.engine.cards import Card, CardKind, PropertyColor
from dbreaker.engine.player import PlayerState
from dbreaker.engine.state import _player_digest


def test_player_digest_property_order_matches_value_strings() -> None:
    """Ensure property rows stay sorted as before (by color string / StrEnum value order)."""
    red = Card(
        id="c-red", name="red", kind=CardKind.PROPERTY, value=3, color=PropertyColor.RED
    )
    brown = Card(
        id="c-br", name="br", kind=CardKind.PROPERTY, value=1, color=PropertyColor.BROWN
    )
    player = PlayerState(
        id="P1",
        name="P1",
        properties={PropertyColor.RED: [red], PropertyColor.BROWN: [brown]},
    )
    dig = _player_digest(player)
    prop_rows = dig[3]
    assert [row[0] for row in prop_rows] == [
        PropertyColor.BROWN.value,
        PropertyColor.RED.value,
    ]

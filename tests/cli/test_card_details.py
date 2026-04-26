from io import StringIO

from rich.console import Console

from dbreaker.cli.renderer import card_details_rich
from dbreaker.engine.cards import create_standard_deck


def test_card_details_renders_yellow_3() -> None:
    deck = create_standard_deck()
    marvin = next(c for c in deck if c.id == "yellow-3")
    buf = StringIO()
    console = Console(
        file=buf,
        width=100,
        color_system=None,
        force_terminal=False,
    )
    console.print(card_details_rich(marvin))
    out = buf.getvalue()
    assert "Marvin" in out
    assert "yellow" in out.lower()

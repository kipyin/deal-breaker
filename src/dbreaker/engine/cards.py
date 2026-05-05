from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CardKind(StrEnum):
    MONEY = "money"
    PROPERTY = "property"
    WILD_PROPERTY = "wild_property"
    RENT = "rent"
    ACTION = "action"


class PropertyColor(StrEnum):
    BROWN = "brown"
    LIGHT_BLUE = "light_blue"
    PINK = "pink"
    ORANGE = "orange"
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    RAILROAD = "railroad"
    UTILITY = "utility"
    ANY = "any"


class ActionSubtype(StrEnum):
    DEAL_BREAKER = "deal_breaker"
    SLY_DEAL = "sly_deal"
    FORCED_DEAL = "forced_deal"
    DEBT_COLLECTOR = "debt_collector"
    JUST_SAY_NO = "just_say_no"
    DOUBLE_THE_RENT = "double_the_rent"
    PASS_GO = "pass_go"
    HOUSE = "house"
    HOTEL = "hotel"
    ITS_MY_BIRTHDAY = "its_my_birthday"


SET_SIZE_BY_COLOR: dict[PropertyColor, int] = {
    PropertyColor.BROWN: 2,
    PropertyColor.LIGHT_BLUE: 3,
    PropertyColor.PINK: 3,
    PropertyColor.ORANGE: 3,
    PropertyColor.RED: 3,
    PropertyColor.YELLOW: 3,
    PropertyColor.GREEN: 3,
    PropertyColor.BLUE: 2,
    PropertyColor.RAILROAD: 4,
    PropertyColor.UTILITY: 2,
}

RENT_LADDER_BY_COLOR: dict[PropertyColor, tuple[int, ...]] = {
    PropertyColor.BROWN: (1, 2),
    PropertyColor.LIGHT_BLUE: (1, 2, 3),
    PropertyColor.PINK: (1, 3, 5),
    PropertyColor.ORANGE: (1, 3, 5),
    PropertyColor.RED: (2, 3, 6),
    PropertyColor.YELLOW: (2, 3, 6),
    PropertyColor.GREEN: (2, 4, 7),
    PropertyColor.BLUE: (3, 8),
    PropertyColor.RAILROAD: (1, 2, 3, 4),
    PropertyColor.UTILITY: (1, 2),
}

BUILDABLE_COLORS: frozenset[PropertyColor] = frozenset(
    {
        PropertyColor.BROWN,
        PropertyColor.LIGHT_BLUE,
        PropertyColor.PINK,
        PropertyColor.ORANGE,
        PropertyColor.RED,
        PropertyColor.YELLOW,
        PropertyColor.GREEN,
        PropertyColor.BLUE,
    }
)

ACTION_COUNT_BY_SUBTYPE: dict[ActionSubtype, int] = {
    ActionSubtype.DEAL_BREAKER: 2,
    ActionSubtype.SLY_DEAL: 3,
    ActionSubtype.FORCED_DEAL: 3,
    ActionSubtype.DEBT_COLLECTOR: 3,
    ActionSubtype.JUST_SAY_NO: 3,
    ActionSubtype.DOUBLE_THE_RENT: 2,
    ActionSubtype.PASS_GO: 10,
    ActionSubtype.HOUSE: 3,
    ActionSubtype.HOTEL: 2,
    ActionSubtype.ITS_MY_BIRTHDAY: 3,
}


@dataclass(frozen=True, slots=True)
class Card:
    id: str
    name: str
    kind: CardKind
    value: int
    color: PropertyColor | None = None
    colors: tuple[PropertyColor, ...] = ()
    action_subtype: ActionSubtype | None = None

    @property
    def playable_colors(self) -> tuple[PropertyColor, ...]:
        if self.kind == CardKind.PROPERTY and self.color is not None:
            return (self.color,)
        return self.colors


def create_standard_deck() -> list[Card]:
    """Return the stable 106-card playable Monopoly Deal deck."""
    cards: list[Card] = []

    def add_many(
        *,
        count: int,
        base_id: str,
        name: str,
        kind: CardKind,
        value: int,
        color: PropertyColor | None = None,
        colors: tuple[PropertyColor, ...] = (),
        action_subtype: ActionSubtype | None = None,
    ) -> None:
        for index in range(count):
            suffix = index + 1
            cards.append(
                Card(
                    id=f"{base_id}-{suffix}",
                    name=name,
                    kind=kind,
                    value=value,
                    color=color,
                    colors=colors,
                    action_subtype=action_subtype,
                )
            )

    for value, count in [(1, 6), (2, 5), (3, 3), (4, 3), (5, 2), (10, 1)]:
        add_many(
            count=count,
            base_id=f"money-{value}",
            name=f"${value}",
            kind=CardKind.MONEY,
            value=value,
        )

    properties = [
        ("brown-1", "Mediterranean Avenue", 1, PropertyColor.BROWN),
        ("brown-2", "Baltic Avenue", 1, PropertyColor.BROWN),
        ("light-blue-1", "Oriental Avenue", 1, PropertyColor.LIGHT_BLUE),
        ("light-blue-2", "Vermont Avenue", 1, PropertyColor.LIGHT_BLUE),
        ("light-blue-3", "Connecticut Avenue", 1, PropertyColor.LIGHT_BLUE),
        ("pink-1", "St. Charles Place", 2, PropertyColor.PINK),
        ("pink-2", "States Avenue", 2, PropertyColor.PINK),
        ("pink-3", "Virginia Avenue", 2, PropertyColor.PINK),
        ("orange-1", "St. James Place", 2, PropertyColor.ORANGE),
        ("orange-2", "Tennessee Avenue", 2, PropertyColor.ORANGE),
        ("orange-3", "New York Avenue", 2, PropertyColor.ORANGE),
        ("red-1", "Illinois Avenue", 3, PropertyColor.RED),
        ("red-2", "Indiana Avenue", 3, PropertyColor.RED),
        ("red-3", "Kentucky Avenue", 3, PropertyColor.RED),
        ("yellow-1", "Atlantic Avenue", 3, PropertyColor.YELLOW),
        ("yellow-2", "Ventnor Avenue", 3, PropertyColor.YELLOW),
        ("yellow-3", "Marvin Gardens", 3, PropertyColor.YELLOW),
        ("green-1", "Pacific Avenue", 4, PropertyColor.GREEN),
        ("green-2", "North Carolina Avenue", 4, PropertyColor.GREEN),
        ("green-3", "Pennsylvania Avenue", 4, PropertyColor.GREEN),
        ("blue-1", "Boardwalk", 4, PropertyColor.BLUE),
        ("blue-2", "Park Place", 4, PropertyColor.BLUE),
        ("railroad-1", "Reading Railroad", 2, PropertyColor.RAILROAD),
        ("railroad-2", "Pennsylvania Railroad", 2, PropertyColor.RAILROAD),
        ("railroad-3", "B. & O. Railroad", 2, PropertyColor.RAILROAD),
        ("railroad-4", "Short Line", 2, PropertyColor.RAILROAD),
        ("utility-1", "Electric Company", 2, PropertyColor.UTILITY),
        ("utility-2", "Water Works", 2, PropertyColor.UTILITY),
    ]
    for card_id, name, value, color in properties:
        cards.append(Card(id=card_id, name=name, kind=CardKind.PROPERTY, value=value, color=color))

    wilds = [
        (
            1,
            "wild-brown-light-blue",
            "Wild Property Brown/Light Blue",
            1,
            (PropertyColor.BROWN, PropertyColor.LIGHT_BLUE),
        ),
        (
            2,
            "wild-pink-orange",
            "Wild Property Pink/Orange",
            2,
            (PropertyColor.PINK, PropertyColor.ORANGE),
        ),
        (
            2,
            "wild-red-yellow",
            "Wild Property Red/Yellow",
            3,
            (PropertyColor.RED, PropertyColor.YELLOW),
        ),
        (
            1,
            "wild-green-railroad",
            "Wild Property Green/Railroad",
            4,
            (PropertyColor.GREEN, PropertyColor.RAILROAD),
        ),
        (
            2,
            "wild-blue-green",
            "Wild Property Blue/Green",
            4,
            (PropertyColor.BLUE, PropertyColor.GREEN),
        ),
        (
            1,
            "wild-railroad-utility",
            "Wild Property Railroad/Utility",
            2,
            (PropertyColor.RAILROAD, PropertyColor.UTILITY),
        ),
        (2, "wild-any", "Wild Property Any", 0, tuple(SET_SIZE_BY_COLOR)),
    ]
    for count, card_id, name, value, colors in wilds:
        add_many(
            count=count,
            base_id=card_id,
            name=name,
            kind=CardKind.WILD_PROPERTY,
            value=value,
            colors=colors,
        )

    rent_cards = [
        (
            2,
            "rent-brown-light-blue",
            "Rent Brown/Light Blue",
            (PropertyColor.BROWN, PropertyColor.LIGHT_BLUE),
        ),
        (2, "rent-pink-orange", "Rent Pink/Orange", (PropertyColor.PINK, PropertyColor.ORANGE)),
        (2, "rent-red-yellow", "Rent Red/Yellow", (PropertyColor.RED, PropertyColor.YELLOW)),
        (2, "rent-green-blue", "Rent Green/Blue", (PropertyColor.GREEN, PropertyColor.BLUE)),
        (
            2,
            "rent-railroad-utility",
            "Rent Railroad/Utility",
            (PropertyColor.RAILROAD, PropertyColor.UTILITY),
        ),
        (3, "rent-any", "Rent Any", (PropertyColor.ANY,)),
    ]
    for count, card_id, name, colors in rent_cards:
        add_many(
            count=count,
            base_id=card_id,
            name=name,
            kind=CardKind.RENT,
            value=1,
            colors=colors,
        )

    action_cards = {
        ActionSubtype.DEAL_BREAKER: ("deal-breaker", "Deal Breaker", 5),
        ActionSubtype.SLY_DEAL: ("sly-deal", "Sly Deal", 3),
        ActionSubtype.FORCED_DEAL: ("forced-deal", "Forced Deal", 3),
        ActionSubtype.DEBT_COLLECTOR: ("debt-collector", "Debt Collector", 3),
        ActionSubtype.JUST_SAY_NO: ("just-say-no", "Just Say No", 4),
        ActionSubtype.DOUBLE_THE_RENT: ("double-rent", "Double The Rent", 1),
        ActionSubtype.PASS_GO: ("pass-go", "Pass Go", 1),
        ActionSubtype.HOUSE: ("house", "House", 3),
        ActionSubtype.HOTEL: ("hotel", "Hotel", 4),
        ActionSubtype.ITS_MY_BIRTHDAY: ("birthday", "It's My Birthday", 2),
    }
    for subtype, count in ACTION_COUNT_BY_SUBTYPE.items():
        card_id, name, value = action_cards[subtype]
        add_many(
            count=count,
            base_id=card_id,
            name=name,
            kind=CardKind.ACTION,
            value=value,
            action_subtype=subtype,
        )

    return cards


def _natural_property_counts_from_deck() -> dict[PropertyColor, int]:
    tallies: dict[PropertyColor, int] = {}
    for card in create_standard_deck():
        if card.kind == CardKind.PROPERTY and card.color is not None:
            tallies[card.color] = tallies.get(card.color, 0) + 1
    return tallies


NATURAL_PROPERTY_COUNT_BY_COLOR: dict[PropertyColor, int] = _natural_property_counts_from_deck()


def _wild_property_deck_count() -> int:
    return sum(1 for card in create_standard_deck() if card.kind == CardKind.WILD_PROPERTY)


WILD_PROPERTY_DECK_TOTAL: int = _wild_property_deck_count()

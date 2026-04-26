from __future__ import annotations

from dataclasses import dataclass, field

from dbreaker.engine.cards import (
    BUILDABLE_COLORS,
    SET_SIZE_BY_COLOR,
    ActionSubtype,
    Card,
    CardKind,
    PropertyColor,
)


@dataclass(slots=True)
class PlayerState:
    id: str
    name: str
    hand: list[Card] = field(default_factory=list)
    bank: list[Card] = field(default_factory=list)
    properties: dict[PropertyColor, list[Card]] = field(default_factory=dict)
    property_attachments: dict[PropertyColor, list[Card]] = field(default_factory=dict)

    def add_to_hand(self, card: Card) -> PlayerState:
        return PlayerState(
            id=self.id,
            name=self.name,
            hand=[*self.hand, card],
            bank=list(self.bank),
            properties={color: list(cards) for color, cards in self.properties.items()},
            property_attachments={
                color: list(cards) for color, cards in self.property_attachments.items()
            },
        )

    def remove_from_hand(self, card_id: str) -> tuple[PlayerState, Card | None]:
        remaining: list[Card] = []
        removed: Card | None = None
        for card in self.hand:
            if card.id == card_id and removed is None:
                removed = card
            else:
                remaining.append(card)
        return (
            PlayerState(
                id=self.id,
                name=self.name,
                hand=remaining,
                bank=list(self.bank),
                properties={color: list(cards) for color, cards in self.properties.items()},
                property_attachments={
                    color: list(cards) for color, cards in self.property_attachments.items()
                },
            ),
            removed,
        )

    def add_to_bank(self, card: Card) -> PlayerState:
        return PlayerState(
            id=self.id,
            name=self.name,
            hand=list(self.hand),
            bank=[*self.bank, card],
            properties={color: list(cards) for color, cards in self.properties.items()},
            property_attachments={
                color: list(cards) for color, cards in self.property_attachments.items()
            },
        )

    def add_property(self, card: Card, color: PropertyColor) -> PlayerState:
        properties = {
            existing_color: list(cards) for existing_color, cards in self.properties.items()
        }
        properties.setdefault(color, []).append(card)
        return PlayerState(
            id=self.id,
            name=self.name,
            hand=list(self.hand),
            bank=list(self.bank),
            properties=properties,
            property_attachments={
                existing_color: list(cards)
                for existing_color, cards in self.property_attachments.items()
            },
        )

    def add_property_attachment(self, card: Card, color: PropertyColor) -> PlayerState:
        attachments = {
            existing_color: list(cards)
            for existing_color, cards in self.property_attachments.items()
        }
        attachments.setdefault(color, []).append(card)
        return PlayerState(
            id=self.id,
            name=self.name,
            hand=list(self.hand),
            bank=list(self.bank),
            properties={
                existing_color: list(cards) for existing_color, cards in self.properties.items()
            },
            property_attachments=attachments,
        )

    def remove_asset(self, card_id: str) -> tuple[PlayerState, Card | None, PropertyColor | None]:
        bank = list(self.bank)
        for index, card in enumerate(bank):
            if card.id == card_id:
                del bank[index]
                return (
                    PlayerState(
                        id=self.id,
                        name=self.name,
                        hand=list(self.hand),
                        bank=bank,
                        properties={color: list(cards) for color, cards in self.properties.items()},
                        property_attachments={
                            color: list(cards) for color, cards in self.property_attachments.items()
                        },
                    ),
                    card,
                    None,
                )

        properties = {color: list(cards) for color, cards in self.properties.items()}
        for color, cards in properties.items():
            for index, card in enumerate(cards):
                if card.id == card_id:
                    del cards[index]
                    return (
                        PlayerState(
                            id=self.id,
                            name=self.name,
                            hand=list(self.hand),
                            bank=list(self.bank),
                            properties=properties,
                            property_attachments={
                                attachment_color: list(attachments)
                                for attachment_color, attachments in (
                                    self.property_attachments.items()
                                )
                            },
                        ),
                        card,
                        color,
                    )

        attachments = {color: list(cards) for color, cards in self.property_attachments.items()}
        for _color, cards in attachments.items():
            for index, card in enumerate(cards):
                if card.id == card_id:
                    del cards[index]
                    return (
                        PlayerState(
                            id=self.id,
                            name=self.name,
                            hand=list(self.hand),
                            bank=list(self.bank),
                            properties={
                                property_color: list(property_cards)
                                for property_color, property_cards in self.properties.items()
                            },
                            property_attachments=attachments,
                        ),
                        card,
                        None,
                    )
        return self, None, None

    def remove_property_set(
        self, color: PropertyColor
    ) -> tuple[PlayerState, list[Card], list[Card]]:
        properties = {
            existing_color: list(cards) for existing_color, cards in self.properties.items()
        }
        attachments = {
            existing_color: list(cards)
            for existing_color, cards in self.property_attachments.items()
        }
        cards = properties.pop(color, [])
        set_attachments = attachments.pop(color, [])
        return (
            PlayerState(
                id=self.id,
                name=self.name,
                hand=list(self.hand),
                bank=list(self.bank),
                properties=properties,
                property_attachments=attachments,
            ),
            cards,
            set_attachments,
        )

    def set_property_color(self, card_id: str, color: PropertyColor) -> PlayerState | None:
        current_color: PropertyColor | None = None
        found: Card | None = None
        properties = {
            existing_color: list(cards) for existing_color, cards in self.properties.items()
        }
        for existing_color, cards in properties.items():
            for index, card in enumerate(cards):
                if card.id == card_id:
                    current_color = existing_color
                    found = card
                    del cards[index]
                    break
            if found is not None:
                break
        if found is None or color not in found.playable_colors:
            return None
        properties.setdefault(color, []).append(found)
        attachments = {
            existing_color: list(cards)
            for existing_color, cards in self.property_attachments.items()
        }
        if current_color is not None and not properties.get(current_color):
            properties.pop(current_color, None)
        return PlayerState(
            id=self.id,
            name=self.name,
            hand=list(self.hand),
            bank=list(self.bank),
            properties=properties,
            property_attachments=attachments,
        )

    def completed_set_count(self) -> int:
        completed = 0
        for color, cards in self.properties.items():
            needed = SET_SIZE_BY_COLOR.get(color)
            if needed is not None and len(cards) >= needed:
                completed += 1
        return completed

    @property
    def asset_value(self) -> int:
        property_value = sum(card.value for cards in self.properties.values() for card in cards)
        attachment_value = sum(
            card.value for cards in self.property_attachments.values() for card in cards
        )
        bank_value = sum(card.value for card in self.bank)
        return property_value + attachment_value + bank_value

    def is_full_set(self, color: PropertyColor) -> bool:
        needed = SET_SIZE_BY_COLOR.get(color)
        return needed is not None and len(self.properties.get(color, [])) >= needed

    def can_build(self, color: PropertyColor, subtype: ActionSubtype) -> bool:
        if color not in BUILDABLE_COLORS or not self.is_full_set(color):
            return False
        attachments = self.property_attachments.get(color, [])
        has_house = any(card.action_subtype == ActionSubtype.HOUSE for card in attachments)
        has_hotel = any(card.action_subtype == ActionSubtype.HOTEL for card in attachments)
        if subtype == ActionSubtype.HOUSE:
            return not has_house
        if subtype == ActionSubtype.HOTEL:
            return has_house and not has_hotel
        return False

    def assets(self) -> list[tuple[Card, PropertyColor | None]]:
        assets: list[tuple[Card, PropertyColor | None]] = [(card, None) for card in self.bank]
        for color, cards in self.properties.items():
            assets.extend((card, color) for card in cards)
        for cards in self.property_attachments.values():
            assets.extend((card, None) for card in cards)
        return assets

    def non_full_property_assets(self) -> list[tuple[Card, PropertyColor]]:
        assets: list[tuple[Card, PropertyColor]] = []
        for color, cards in self.properties.items():
            if not self.is_full_set(color):
                assets.extend(
                    (card, color)
                    for card in cards
                    if card.kind in {CardKind.PROPERTY, CardKind.WILD_PROPERTY}
                )
        return assets

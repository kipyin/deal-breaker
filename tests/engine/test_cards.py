from dbreaker.engine.cards import CardKind, PropertyColor, create_standard_deck


def test_standard_deck_has_stable_unique_cards_and_core_types() -> None:
    deck = create_standard_deck()

    assert len(deck) > 0
    assert len({card.id for card in deck}) == len(deck)
    assert {card.kind for card in deck} >= {
        CardKind.MONEY,
        CardKind.PROPERTY,
        CardKind.RENT,
        CardKind.ACTION,
        CardKind.WILD_PROPERTY,
    }
    assert any(card.name == "Deal Breaker" for card in deck)
    assert any(card.color == PropertyColor.BLUE for card in deck)

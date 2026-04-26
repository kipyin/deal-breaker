from __future__ import annotations

import random

from dbreaker.engine.cards import Card, create_standard_deck


def shuffled_standard_deck(seed: int | None = None) -> list[Card]:
    deck = create_standard_deck()
    random.Random(seed).shuffle(deck)
    return deck

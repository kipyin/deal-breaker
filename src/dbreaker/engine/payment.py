from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from dbreaker.engine.cards import Card
from dbreaker.engine.player import PlayerState


@dataclass(frozen=True, slots=True)
class PaymentSelection:
    cards: list[Card]

    @property
    def total_value(self) -> int:
        return sum(card.value for card in self.cards)


def choose_payment(player: PlayerState, amount: int) -> PaymentSelection:
    selections = legal_payment_selections(player, amount=amount)
    if not selections:
        return PaymentSelection(cards=[])
    return min(
        selections, key=lambda selection: (selection.total_value < amount, selection.total_value)
    )


def legal_payment_selections(player: PlayerState, amount: int) -> list[PaymentSelection]:
    assets = [card for card, _color in player.assets() if card.value > 0]
    if not assets:
        return [PaymentSelection(cards=[])]
    total_assets = sum(card.value for card in assets)
    if total_assets <= amount:
        return [PaymentSelection(cards=assets)]

    selections: dict[tuple[str, ...], PaymentSelection] = {}
    max_group_size = min(len(assets), 8)
    for group_size in range(1, max_group_size + 1):
        for group in combinations(assets, group_size):
            total = sum(card.value for card in group)
            if total >= amount:
                key = tuple(sorted(card.id for card in group))
                selections[key] = PaymentSelection(cards=list(group))
    if not selections:
        # e.g. debt needs 9+ small bills but only 8 are enumerated above — paying all
        # assets is always a legal overpay when total_assets > amount.
        return [PaymentSelection(cards=assets)]
    return sorted(
        selections.values(),
        key=lambda selection: (
            selection.total_value,
            len(selection.cards),
            tuple(card.id for card in selection.cards),
        ),
    )

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


def _payable_bank(player: PlayerState) -> list[Card]:
    return [card for card in player.bank if card.value > 0]


def _payable_property_assets(player: PlayerState) -> list[Card]:
    out: list[Card] = []
    for cards in player.properties.values():
        out.extend(card for card in cards if card.value > 0)
    for cards in player.property_attachments.values():
        out.extend(card for card in cards if card.value > 0)
    return out


def _bank_by_value(bank_cards: list[Card]) -> dict[int, list[Card]]:
    by_value: dict[int, list[Card]] = {}
    for card in bank_cards:
        by_value.setdefault(card.value, []).append(card)
    for cards in by_value.values():
        cards.sort(key=lambda c: c.id)
    return by_value


def _find_asset_card(player: PlayerState, card_id: str) -> Card | None:
    for card in player.bank:
        if card.id == card_id:
            return card
    for cards in player.properties.values():
        for card in cards:
            if card.id == card_id:
                return card
    for cards in player.property_attachments.values():
        for card in cards:
            if card.id == card_id:
                return card
    return None


def is_legal_payment_selection(
    player: PlayerState, card_ids: tuple[str, ...], amount: int
) -> bool:
    """True if the payer owns these distinct assets and their total value covers the debt."""
    if amount <= 0:
        return len(card_ids) == 0
    bank_cards = _payable_bank(player)
    prop_cards = _payable_property_assets(player)
    all_payable = bank_cards + prop_cards
    if not card_ids:
        return len(all_payable) == 0
    seen: set[str] = set()
    total = 0
    for cid in card_ids:
        if cid in seen:
            return False
        seen.add(cid)
        card = _find_asset_card(player, cid)
        if card is None or card.value <= 0:
            return False
        total += card.value
    return total >= amount


def _reachable_bank_sums(bank_by_value: dict[int, list[Card]]) -> set[int]:
    reachable: set[int] = {0}
    for value in sorted(bank_by_value.keys()):
        cnt = len(bank_by_value[value])
        new_reachable: set[int] = set()
        for base in reachable:
            for take in range(0, cnt + 1):
                new_reachable.add(base + take * value)
        reachable = new_reachable
    return reachable


def _min_bank_sum_at_least(bank_by_value: dict[int, list[Card]], need: int) -> int | None:
    if need <= 0:
        return 0
    reachable = _reachable_bank_sums(bank_by_value)
    candidates = [s for s in reachable if s >= need]
    return min(candidates) if candidates else None


def _enumerate_bank_multisets_for_sum(
    bank_by_value: dict[int, list[Card]], target_sum: int
) -> list[dict[int, int]]:
    if target_sum == 0:
        return [{}]
    values = sorted(bank_by_value.keys(), reverse=True)
    results: list[dict[int, int]] = []

    def dfs(i: int, rem: int, acc: dict[int, int]) -> None:
        if rem == 0:
            results.append(dict(acc))
            return
        if i >= len(values):
            return
        v = values[i]
        max_take = min(len(bank_by_value[v]), rem // v)
        for take in range(0, max_take + 1):
            if take:
                acc[v] = take
            dfs(i + 1, rem - take * v, acc)
            if take:
                del acc[v]

    dfs(0, target_sum, {})
    return results


def _resolve_bank_multiset(
    bank_by_value: dict[int, list[Card]], multiset: dict[int, int]
) -> list[Card]:
    out: list[Card] = []
    for value in sorted(multiset.keys()):
        take = multiset[value]
        out.extend(bank_by_value[value][:take])
    return out


def _property_subsets(prop_cards: list[Card]) -> list[list[Card]]:
    n = len(prop_cards)
    if n == 0:
        return [[]]
    if n <= 22:
        return [
            [prop_cards[i] for i in range(n) if mask & (1 << i)]
            for mask in range(1 << n)
        ]
    subsets: list[list[Card]] = [[]]
    for r in range(1, min(n, 22) + 1):
        for combo in combinations(range(n), r):
            subsets.append([prop_cards[i] for i in combo])
    return subsets


def legal_payment_selections(player: PlayerState, amount: int) -> list[PaymentSelection]:
    bank_cards = _payable_bank(player)
    prop_cards = _payable_property_assets(player)
    all_payable = bank_cards + prop_cards

    if not all_payable:
        return [PaymentSelection(cards=[])]

    total_assets = sum(card.value for card in all_payable)
    if total_assets <= amount:
        return [PaymentSelection(cards=list(all_payable))]

    bank_by_value = _bank_by_value(bank_cards)
    selections_by_key: dict[tuple[str, ...], PaymentSelection] = {}
    min_total: int | None = None

    for chosen_props in _property_subsets(prop_cards):
        prop_sum = sum(c.value for c in chosen_props)
        bank_need = amount - prop_sum

        if bank_need <= 0:
            candidate_total = prop_sum
            bank_multisets: list[dict[int, int]] = [{}]
        else:
            min_bank = _min_bank_sum_at_least(bank_by_value, bank_need)
            if min_bank is None:
                continue
            bank_multisets = _enumerate_bank_multisets_for_sum(bank_by_value, min_bank)
            if not bank_multisets:
                continue
            candidate_total = prop_sum + min_bank

        if min_total is None or candidate_total < min_total:
            min_total = candidate_total
            selections_by_key.clear()

        if candidate_total != min_total:
            continue

        for multiset in bank_multisets:
            bank_concrete = _resolve_bank_multiset(bank_by_value, multiset)
            cards = list(chosen_props) + bank_concrete
            key = tuple(sorted(c.id for c in cards))
            selections_by_key[key] = PaymentSelection(cards=cards)

    if not selections_by_key:
        return [PaymentSelection(cards=list(all_payable))]

    return sorted(
        selections_by_key.values(),
        key=lambda selection: (
            selection.total_value,
            len(selection.cards),
            tuple(card.id for card in selection.cards),
        ),
    )

from dbreaker.engine.cards import Card, CardKind, PropertyColor
from dbreaker.engine.payment import (
    choose_payment,
    is_legal_payment_selection,
    legal_payment_selections,
)
from dbreaker.engine.player import PlayerState


def test_choose_payment_allows_overpay_without_making_change() -> None:
    player = PlayerState(id="P1", name="P1")
    player = player.add_to_bank(Card(id="money-1", name="$1", kind=CardKind.MONEY, value=1))
    player = player.add_to_bank(Card(id="money-5", name="$5", kind=CardKind.MONEY, value=5))

    payment = choose_payment(player, amount=3)

    assert [card.id for card in payment.cards] == ["money-5"]
    assert payment.total_value == 5


def test_legal_payment_includes_all_assets_when_nine_plus_small_bills_required() -> None:
    """Debt needs more than 8 $1s; must still yield a legal pay of all bills."""
    player = PlayerState(id="P1", name="P1")
    for i in range(9):
        player = player.add_to_bank(
            Card(id=f"bill-{i}", name="$1", kind=CardKind.MONEY, value=1)
        )

    selections = legal_payment_selections(player, amount=9)

    assert len(selections) >= 1
    assert {card.id for card in selections[0].cards} == {f"bill-{i}" for i in range(9)}
    assert sum(card.value for card in selections[0].cards) >= 9


def test_many_same_value_bank_cards_do_not_explode_selection_count() -> None:
    player = PlayerState(id="P1", name="P1")
    for i in range(20):
        player = player.add_to_bank(
            Card(id=f"one-{i}", name="$1", kind=CardKind.MONEY, value=1)
        )
    selections = legal_payment_selections(player, amount=5)
    assert len(selections) == 1
    assert len(selections[0].cards) == 5
    assert selections[0].total_value == 5


def test_is_legal_accepts_any_distinct_bank_cards_with_same_face_value() -> None:
    player = PlayerState(id="P1", name="P1")
    for i in range(5):
        player = player.add_to_bank(
            Card(id=f"one-{i}", name="$1", kind=CardKind.MONEY, value=1)
        )
    assert is_legal_payment_selection(player, ("one-3", "one-4"), amount=2) is True
    assert is_legal_payment_selection(player, ("one-3", "one-3"), amount=2) is False


def test_is_legal_allows_empty_pay_when_player_has_no_payable_assets() -> None:
    player = PlayerState(id="P2", name="P2")
    assert is_legal_payment_selection(player, (), amount=3) is True
    assert is_legal_payment_selection(player, (), amount=0) is True


def test_minimum_total_prefers_exact_payment_when_possible() -> None:
    player = PlayerState(id="P1", name="P1")
    player = player.add_to_bank(Card(id="a", name="$2", kind=CardKind.MONEY, value=2))
    player = player.add_to_bank(Card(id="b", name="$3", kind=CardKind.MONEY, value=3))
    player = player.add_to_bank(Card(id="c", name="$10", kind=CardKind.MONEY, value=10))
    selections = legal_payment_selections(player, amount=5)
    ids_sets = {tuple(sorted(c.id for c in s.cards)) for s in selections}
    assert ("a", "b") in ids_sets
    assert ("c",) not in ids_sets
    assert all(s.total_value == 5 for s in selections)


def test_minimum_total_smallest_overpay_when_exact_impossible() -> None:
    player = PlayerState(id="P1", name="P1")
    player = player.add_to_bank(Card(id="a", name="$4", kind=CardKind.MONEY, value=4))
    player = player.add_to_bank(Card(id="b", name="$10", kind=CardKind.MONEY, value=10))
    selections = legal_payment_selections(player, amount=5)
    assert len(selections) == 1
    assert {c.id for c in selections[0].cards} == {"b"}
    assert selections[0].total_value == 10


def test_property_cards_remain_distinct_in_selections() -> None:
    p1 = Card(id="blue-1", name="Blue 1", kind=CardKind.PROPERTY, value=3, color=PropertyColor.BLUE)
    p2 = Card(
        id="rail-1", name="RR", kind=CardKind.PROPERTY, value=1, color=PropertyColor.RAILROAD
    )
    player = PlayerState(
        id="P1",
        name="P1",
        bank=[
            Card(id="m5", name="$5", kind=CardKind.MONEY, value=5),
        ],
        properties={PropertyColor.BLUE: [p1], PropertyColor.RAILROAD: [p2]},
    )
    selections = legal_payment_selections(player, amount=4)
    assert len(selections) == 1
    assert {c.id for c in selections[0].cards} == {"blue-1", "rail-1"}


def test_large_bank_pile_keeps_few_canonical_selections() -> None:
    player = PlayerState(id="P1", name="P1")
    for i in range(15):
        player = player.add_to_bank(
            Card(id=f"o-{i}", name="$1", kind=CardKind.MONEY, value=1)
        )
    for i in range(15):
        player = player.add_to_bank(
            Card(id=f"t-{i}", name="$2", kind=CardKind.MONEY, value=2)
        )
    selections = legal_payment_selections(player, amount=7)
    assert len(selections) <= 20
    assert all(s.total_value == 7 for s in selections)

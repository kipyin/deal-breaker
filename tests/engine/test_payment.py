from dbreaker.engine.cards import Card, CardKind
from dbreaker.engine.payment import choose_payment, legal_payment_selections
from dbreaker.engine.player import PlayerState


def test_choose_payment_allows_overpay_without_making_change() -> None:
    player = PlayerState(id="P1", name="P1")
    player = player.add_to_bank(Card(id="money-1", name="$1", kind=CardKind.MONEY, value=1))
    player = player.add_to_bank(Card(id="money-5", name="$5", kind=CardKind.MONEY, value=5))

    payment = choose_payment(player, amount=3)

    assert [card.id for card in payment.cards] == ["money-5"]
    assert payment.total_value == 5


def test_legal_payment_includes_all_assets_when_nine_plus_small_bills_required() -> None:
    """Debt needs more than 8 $1s; 8-combination search must still yield a legal pay."""
    player = PlayerState(id="P1", name="P1")
    for i in range(9):
        player = player.add_to_bank(
            Card(id=f"bill-{i}", name="$1", kind=CardKind.MONEY, value=1)
        )

    selections = legal_payment_selections(player, amount=9)

    assert len(selections) >= 1
    assert {card.id for card in selections[0].cards} == {f"bill-{i}" for i in range(9)}
    assert sum(card.value for card in selections[0].cards) >= 9

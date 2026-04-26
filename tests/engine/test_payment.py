from dbreaker.engine.cards import Card, CardKind
from dbreaker.engine.payment import choose_payment
from dbreaker.engine.player import PlayerState


def test_choose_payment_allows_overpay_without_making_change() -> None:
    player = PlayerState(id="P1", name="P1")
    player = player.add_to_bank(Card(id="money-1", name="$1", kind=CardKind.MONEY, value=1))
    player = player.add_to_bank(Card(id="money-5", name="$5", kind=CardKind.MONEY, value=5))

    payment = choose_payment(player, amount=3)

    assert [card.id for card in payment.cards] == ["money-5"]
    assert payment.total_value == 5

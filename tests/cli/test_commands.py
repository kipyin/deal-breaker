from dbreaker.cli.commands import parse_command
from dbreaker.engine.actions import (
    BankCard,
    DiscardCard,
    EndTurn,
    PayWithAssets,
    PlayActionCard,
    PlayProperty,
    PlayRent,
    RespondJustSayNo,
)
from dbreaker.engine.cards import PropertyColor


def test_parse_bank_and_end_commands() -> None:
    assert parse_command("bank money-1") == BankCard(card_id="money-1")
    assert parse_command("end") == EndTurn()


def test_parse_play_rent_command_with_target() -> None:
    action = parse_command("play rent-blue target P2 color blue double double-1")

    assert action == PlayRent(
        card_id="rent-blue",
        target_player_id="P2",
        color=PropertyColor.BLUE,
        double_rent_card_id="double-1",
    )


def test_parse_pending_and_discard_commands() -> None:
    assert parse_command("pay money-1 prop-2") == PayWithAssets(
        card_ids=("money-1", "prop-2")
    )
    assert parse_command("pay") == PayWithAssets(card_ids=())
    assert parse_command("discard card-1") == DiscardCard(card_id="card-1")
    assert parse_command("accept") == RespondJustSayNo(card_id=None, accept=True)
    assert parse_command("no just-say-no-1") == RespondJustSayNo(
        card_id="just-say-no-1", accept=False
    )


def test_parse_property_and_action_shortcuts() -> None:
    assert parse_command("property prop-1 blue") == PlayProperty(
        card_id="prop-1", color=PropertyColor.BLUE
    )
    assert parse_command("pass-go pass-1") == PlayActionCard(card_id="pass-1")
    assert parse_command("debt debt-1 target P2") == PlayActionCard(
        card_id="debt-1",
        target_player_id="P2",
    )
    assert parse_command("house house-1 blue") == PlayActionCard(
        card_id="house-1",
        color=PropertyColor.BLUE,
    )
    assert parse_command("hotel hotel-1 blue") == PlayActionCard(
        card_id="hotel-1",
        color=PropertyColor.BLUE,
    )
    assert parse_command("deal-breaker breaker-1 target P2 blue") == PlayActionCard(
        card_id="breaker-1",
        target_player_id="P2",
        color=PropertyColor.BLUE,
    )

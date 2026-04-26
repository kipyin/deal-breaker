from dbreaker.engine.actions import BankCard, DrawCards, EndTurn, PlayProperty
from dbreaker.engine.cards import Card, CardKind, PropertyColor
from dbreaker.engine.game import Game


def test_legal_actions_include_banking_property_play_and_end_turn() -> None:
    money = Card(id="money-1", name="$1", kind=CardKind.MONEY, value=1)
    blue = Card(
        id="blue-1",
        name="Boardwalk",
        kind=CardKind.PROPERTY,
        value=4,
        color=PropertyColor.BLUE,
    )
    game = Game.new(player_count=2, seed=7, preset_hands=[[money, blue], []])

    assert game.legal_actions("P1") == [DrawCards()]
    game.step("P1", DrawCards())

    legal_actions = game.legal_actions("P1")

    assert BankCard(card_id="money-1") in legal_actions
    assert PlayProperty(card_id="blue-1", color=PropertyColor.BLUE) in legal_actions
    assert EndTurn() in legal_actions


def test_step_rejects_illegal_action_for_current_player() -> None:
    game = Game.new(player_count=2, seed=7)

    result = game.step("P2", EndTurn())

    assert result.accepted is False
    assert result.events[-1].type == "action_rejected"

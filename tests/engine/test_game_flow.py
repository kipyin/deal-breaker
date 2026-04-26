from dbreaker.engine.actions import BankCard, DrawCards, EndTurn, PlayProperty
from dbreaker.engine.cards import Card, CardKind, PropertyColor
from dbreaker.engine.game import Game
from dbreaker.engine.rules import GamePhase, RuleConfig


def test_basic_turn_flow_records_events_and_advances_player() -> None:
    money = Card(id="money-1", name="$1", kind=CardKind.MONEY, value=1)
    game = Game.new(player_count=2, seed=2, preset_hands=[[money], []])

    game.step("P1", DrawCards())
    bank_result = game.step("P1", BankCard(card_id="money-1"))
    end_result = game.step("P1", EndTurn())

    assert bank_result.accepted is True
    assert end_result.accepted is True
    assert game.state.current_player_id == "P2"
    assert game.state.players["P1"].bank[0].id == "money-1"
    assert [event.type for event in game.event_log][-2:] == ["card_banked", "turn_ended"]


def test_player_wins_after_completing_required_property_sets() -> None:
    cards = [
        Card(
            id="blue-1", name="Boardwalk", kind=CardKind.PROPERTY, value=4, color=PropertyColor.BLUE
        ),
        Card(
            id="blue-2",
            name="Park Place",
            kind=CardKind.PROPERTY,
            value=4,
            color=PropertyColor.BLUE,
        ),
        Card(
            id="green-1", name="Pacific", kind=CardKind.PROPERTY, value=4, color=PropertyColor.GREEN
        ),
        Card(
            id="green-2",
            name="North Carolina",
            kind=CardKind.PROPERTY,
            value=4,
            color=PropertyColor.GREEN,
        ),
        Card(
            id="green-3",
            name="Pennsylvania",
            kind=CardKind.PROPERTY,
            value=4,
            color=PropertyColor.GREEN,
        ),
        Card(id="red-1", name="Illinois", kind=CardKind.PROPERTY, value=3, color=PropertyColor.RED),
        Card(id="red-2", name="Indiana", kind=CardKind.PROPERTY, value=3, color=PropertyColor.RED),
        Card(id="red-3", name="Kentucky", kind=CardKind.PROPERTY, value=3, color=PropertyColor.RED),
    ]
    game = Game.new(
        player_count=2,
        seed=3,
        preset_hands=[cards, []],
        rules=RuleConfig(actions_per_turn=10),
    )
    game.state.phase = GamePhase.ACTION

    for card in cards:
        game.step("P1", PlayProperty(card_id=card.id, color=card.color))

    assert game.state.winner_id == "P1"
    assert game.event_log[-1].type == "game_won"

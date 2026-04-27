from dbreaker.engine.actions import BankCard, DiscardCard, DrawCards, EndTurn, PlayProperty
from dbreaker.engine.cards import Card, CardKind, PropertyColor
from dbreaker.engine.game import Game
from dbreaker.engine.rules import GamePhase, RuleConfig
from dbreaker.engine.state import state_digest


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


def test_over_limit_hand_can_continue_until_actions_are_done() -> None:
    hand = [
        Card(id=f"money-{index}", name="$1", kind=CardKind.MONEY, value=1)
        for index in range(7)
    ]
    game = Game.new(player_count=2, seed=2, preset_hands=[hand, []])
    game.state.deck = [
        Card(id="draw-1", name="$1", kind=CardKind.MONEY, value=1),
        Card(id="draw-2", name="$1", kind=CardKind.MONEY, value=1),
    ]

    game.step("P1", DrawCards())
    assert game.state.phase is GamePhase.ACTION
    assert game.observation_for("P1").discard_required == 2
    assert not any(isinstance(action, DiscardCard) for action in game.legal_actions("P1"))

    game.step("P1", BankCard(card_id="money-0"))

    assert game.state.phase is GamePhase.ACTION
    assert game.observation_for("P1").actions_left == 2
    assert not any(isinstance(action, DiscardCard) for action in game.legal_actions("P1"))


def test_ending_turn_over_hand_limit_enters_discard_phase() -> None:
    hand = [
        Card(id=f"money-{index}", name="$1", kind=CardKind.MONEY, value=1)
        for index in range(8)
    ]
    game = Game.new(player_count=2, seed=2, preset_hands=[hand, []])
    game.state.phase = GamePhase.ACTION

    result = game.step("P1", EndTurn())

    assert result.accepted is True
    assert game.state.current_player_id == "P1"
    assert game.state.phase is GamePhase.DISCARD
    assert not any(isinstance(action, EndTurn) for action in game.legal_actions("P1"))

    game.step("P1", DiscardCard(card_id="money-0"))

    assert game.state.current_player_id == "P2"


def test_discard_phase_at_hand_limit_only_allows_end_turn() -> None:
    hand = [
        Card(id=f"money-{index}", name="$1", kind=CardKind.MONEY, value=1)
        for index in range(7)
    ]
    game = Game.new(player_count=2, seed=2, preset_hands=[hand, []])
    game.state.phase = GamePhase.ACTION
    game.state.actions_taken = game.state.rules.actions_per_turn
    game.state.phase = game.state.next_phase_after_action()

    legal_actions = game.legal_actions("P1")

    assert legal_actions == [EndTurn()]

    discard_result = game.step("P1", DiscardCard(card_id="money-0"))

    assert discard_result.accepted is False
    assert game.state.current_player_id == "P1"
    assert game.state.phase is GamePhase.DISCARD


def test_discard_phase_rejects_end_turn_until_hand_limit_is_met() -> None:
    hand = [
        Card(id=f"money-{index}", name="$1", kind=CardKind.MONEY, value=1)
        for index in range(8)
    ]
    game = Game.new(player_count=2, seed=2, preset_hands=[hand, []])
    game.state.phase = GamePhase.DISCARD

    end_result = game.step("P1", EndTurn())

    assert end_result.accepted is False
    assert game.state.current_player_id == "P1"
    assert game.state.phase is GamePhase.DISCARD

    discard_result = game.step("P1", DiscardCard(card_id="money-0"))

    assert discard_result.accepted is True
    assert game.state.current_player_id == "P2"


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


def test_record_transitions_false_matches_state_and_skips_logs() -> None:
    g_log = Game.new(player_count=2, seed=5)
    g_fast = Game.new(player_count=2, seed=5, record_transitions=False)
    for _ in range(25):
        player_id = g_log.active_player_id
        legal = g_log.legal_actions(player_id)
        assert legal
        action = legal[0]
        r_log = g_log.step(player_id, action)
        r_fast = g_fast.step(player_id, action)
        assert r_log.accepted == r_fast.accepted
        assert state_digest(g_log.state) == state_digest(g_fast.state)
    assert g_fast.action_log == []
    assert g_fast.event_log == []
    assert len(g_log.action_log) == 25

from dbreaker.engine.actions import DrawCards, EndTurn
from dbreaker.engine.game import Game
from dbreaker.strategies.human_like import HumanLikeStrategy


def test_human_like_strategy_returns_legal_action() -> None:
    game = Game.new(player_count=2, seed=9)
    legal = game.legal_actions("P1")
    decision = HumanLikeStrategy().choose_action(game.observation_for("P1"), legal)
    assert decision.action in legal
    assert decision.reason_summary


def test_human_like_in_draw_phase_chooses_draw() -> None:
    game = Game.new(player_count=2, seed=1)
    assert game.state.phase.value == "draw"
    legal = game.legal_actions("P1")
    assert any(isinstance(a, DrawCards) for a in legal)
    decision = HumanLikeStrategy().choose_action(game.observation_for("P1"), legal)
    assert isinstance(decision.action, DrawCards)


def test_human_like_handles_only_end_turn() -> None:
    game = Game.new(player_count=2, seed=3)
    decision = HumanLikeStrategy().choose_action(game.observation_for("P1"), [EndTurn()])
    assert decision.action == EndTurn()

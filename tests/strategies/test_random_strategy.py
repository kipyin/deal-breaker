from dbreaker.engine.actions import EndTurn
from dbreaker.engine.game import Game
from dbreaker.strategies.random import RandomStrategy


def test_random_strategy_returns_one_of_the_legal_actions() -> None:
    game = Game.new(player_count=2, seed=12)
    legal_actions = game.legal_actions("P1")

    decision = RandomStrategy(seed=1).choose_action(game.observation_for("P1"), legal_actions)

    assert decision.action in legal_actions
    assert decision.reason_summary


def test_random_strategy_handles_only_end_turn_action() -> None:
    game = Game.new(player_count=2, seed=12)
    action = EndTurn()

    decision = RandomStrategy(seed=1).choose_action(game.observation_for("P1"), [action])

    assert decision.action == action

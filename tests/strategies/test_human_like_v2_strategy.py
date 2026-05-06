from dbreaker.engine.game import Game
from dbreaker.strategies.human_like_v2 import HumanLikeV2Strategy
from dbreaker.strategies.registry import create_strategy


def test_human_like_v2_registry_name() -> None:
    s = create_strategy("human_like_v2")
    assert s.name == "human_like_v2"


def test_human_like_v2_returns_legal_action() -> None:
    game = Game.new(player_count=3, seed=11)
    legal = game.legal_actions("P1")
    decision = HumanLikeV2Strategy().choose_action(game.observation_for("P1"), legal)
    assert decision.action in legal

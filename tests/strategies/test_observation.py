from dbreaker.engine.game import Game


def test_observation_hides_other_players_hands_by_default() -> None:
    game = Game.new(player_count=2, seed=11)

    observation = game.observation_for("P1")

    assert observation.player_id == "P1"
    assert observation.hand is game.state.players["P1"].hand
    assert observation.opponents["P2"].hand_size == len(game.state.players["P2"].hand)
    assert not hasattr(observation.opponents["P2"], "hand")

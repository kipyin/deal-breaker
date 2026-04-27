from dbreaker.engine.game import Game


def test_observation_hides_other_players_hands_by_default() -> None:
    game = Game.new(player_count=2, seed=11)

    observation = game.observation_for("P1")

    assert observation.player_id == "P1"
    assert observation.hand is game.state.players["P1"].hand
    assert observation.opponents["P2"].hand_size == len(game.state.players["P2"].hand)
    assert not hasattr(observation.opponents["P2"], "hand")


def test_observation_exposes_other_players_public_bank_cards() -> None:
    game = Game.new(player_count=2, seed=11)
    bank_card = game.state.players["P2"].hand.pop()
    game.state.players["P2"].bank.append(bank_card)

    observation = game.observation_for("P1")

    assert observation.opponents["P2"].bank == (bank_card,)
    assert observation.opponents["P2"].bank_value == bank_card.value

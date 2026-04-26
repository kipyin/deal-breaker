from dbreaker.experiments.elo import update_multiplayer_elo


def test_multiplayer_elo_rewards_higher_ranked_players() -> None:
    ratings = {"winner": 1000.0, "second": 1000.0, "third": 1000.0}

    updated = update_multiplayer_elo(ratings, ["winner", "second", "third"], k_factor=32.0)

    assert updated["winner"] > ratings["winner"]
    assert updated["third"] < ratings["third"]
    assert updated["winner"] > updated["second"] > updated["third"]

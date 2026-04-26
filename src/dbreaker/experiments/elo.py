from __future__ import annotations


def update_multiplayer_elo(
    ratings: dict[str, float],
    rankings: list[str],
    *,
    k_factor: float = 24.0,
) -> dict[str, float]:
    updated = dict(ratings)
    for index, player in enumerate(rankings):
        for opponent in rankings[index + 1 :]:
            player_rating = updated[player]
            opponent_rating = updated[opponent]
            expected = 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))
            delta = k_factor * (1 - expected) / max(1, len(rankings) - 1)
            updated[player] += delta
            updated[opponent] -= delta
    return updated

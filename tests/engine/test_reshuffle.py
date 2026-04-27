from __future__ import annotations

from dbreaker.engine.actions import DrawCards
from dbreaker.engine.cards import create_standard_deck
from dbreaker.engine.game import Game
from dbreaker.engine.rules import GamePhase, RuleConfig


def test_draw_reshuffles_discard_when_deck_is_empty() -> None:
    game = Game.new(
        player_count=2,
        seed=7,
        rules=RuleConfig(reshuffle_discard_when_deck_empty=True),
    )
    p1 = game.state.player_order[0]
    start_hand = len(game.state.players[p1].hand)
    game.state.deck.clear()
    deck_cards = create_standard_deck()
    game.state.discard.extend([deck_cards[0], deck_cards[1], deck_cards[2]])
    assert game.state.phase == GamePhase.DRAW

    result = game.step(p1, DrawCards())

    assert result.accepted
    assert game.state.phase == GamePhase.ACTION
    assert len(game.state.players[p1].hand) == start_hand + 2
    assert len(game.state.deck) == 1
    assert game.state.discard == []


def test_draw_with_reshuffle_disabled_does_not_refill_deck() -> None:
    game = Game.new(
        player_count=2,
        seed=7,
        rules=RuleConfig(reshuffle_discard_when_deck_empty=False),
    )
    p1 = game.state.player_order[0]
    start_hand = len(game.state.players[p1].hand)
    game.state.deck.clear()
    deck_cards = create_standard_deck()
    game.state.discard.extend([deck_cards[0], deck_cards[1]])

    result = game.step(p1, DrawCards())

    assert result.accepted
    assert len(game.state.players[p1].hand) == start_hand
    assert game.state.deck == []
    assert len(game.state.discard) == 2


def test_reshuffle_shuffle_is_deterministic_for_identical_state() -> None:
    def draw_two_after_reshuffle() -> list[str]:
        game = Game.new(
            player_count=2,
            seed=42,
            rules=RuleConfig(reshuffle_discard_when_deck_empty=True),
        )
        p1 = game.state.player_order[0]
        pre = [c.id for c in game.state.players[p1].hand]
        game.state.deck.clear()
        for c in create_standard_deck()[:5]:
            game.state.discard.append(c)
        game.step(p1, DrawCards())
        post = [c.id for c in game.state.players[p1].hand]
        return [card_id for card_id in post if card_id not in pre]

    first = draw_two_after_reshuffle()
    second = draw_two_after_reshuffle()
    assert first == second

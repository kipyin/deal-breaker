from dbreaker.engine.actions import EndTurn
from dbreaker.engine.game import Game
from dbreaker.replay.player import replay_actions


def test_replay_actions_reproduces_event_digest() -> None:
    game = Game.new(player_count=2, seed=21)
    game.step("P1", EndTurn())

    replayed = replay_actions(player_count=2, seed=21, actions=[("P1", EndTurn())])

    assert [event.digest() for event in replayed.event_log] == [
        event.digest() for event in game.event_log
    ]

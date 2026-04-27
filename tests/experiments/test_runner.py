from __future__ import annotations

import pytest

from dbreaker.engine.actions import Action
from dbreaker.engine.game import Game
from dbreaker.experiments.runner import run_self_play_game
from dbreaker.strategies.registry import default_registry


def test_run_self_play_aborts_when_no_legal_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No infinite loop in PAYMENT (or any phase) if legal actions are empty."""

    def _empty_legals(_self: Game, _player_id: str) -> list[Action]:
        return []

    monkeypatch.setattr(Game, "legal_actions", _empty_legals)
    r = default_registry()
    result = run_self_play_game(
        game_id="x",
        player_count=2,
        strategies=[r.create("random"), r.create("random")],
        seed=1,
    )
    assert result.ended_by == "aborted"
    assert result.abort_reason is not None


def test_run_self_play_max_turns_without_property_winner() -> None:
    r = default_registry()
    result = run_self_play_game(
        game_id="short",
        player_count=2,
        strategies=[r.create("random"), r.create("random")],
        seed=1,
        max_turns=1,
    )
    assert result.ended_by == "max_turns"
    assert result.max_turns == 1
    assert result.turns > 1
    assert result.self_play_steps > 0


def test_run_self_play_terminates() -> None:
    """A few self-play games finish quickly (heuristic vs heuristic is deterministic, fast)."""
    r = default_registry()
    for i in range(2):
        result = run_self_play_game(
            game_id=f"g{i}",
            player_count=2,
            strategies=[r.create("basic"), r.create("basic")],
            seed=10 + i,
            max_turns=25,
            max_self_play_steps=5_000,
        )
        assert result.ended_by in ("winner", "max_turns", "aborted")

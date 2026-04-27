from __future__ import annotations

import pytest

from dbreaker.engine.actions import Action
from dbreaker.engine.game import Game
from dbreaker.experiments import runner as runner_mod
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
        stalemate_turns=None,
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
        assert result.ended_by in ("winner", "max_turns", "stalemate", "aborted")


def test_run_self_play_stalemate_exits_on_no_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With progress scores forced flat, the runner leaves by stalemate before max turns."""

    def _flat_progress(_game: Game) -> tuple[int, int]:
        return (0, 0)

    monkeypatch.setattr(runner_mod, "_progress_score", _flat_progress)
    r = default_registry()
    result = run_self_play_game(
        game_id="stale",
        player_count=2,
        strategies=[r.create("basic"), r.create("basic")],
        seed=1,
        max_turns=500,
        stalemate_turns=2,
    )
    assert result.ended_by == "stalemate"
    assert result.self_play_steps > 0


def test_run_self_play_random_strategies_are_deterministic_with_seed() -> None:
    r = default_registry()
    a = run_self_play_game(
        game_id="det",
        player_count=2,
        strategies=[r.create("random"), r.create("random")],
        seed=42,
        max_turns=15,
        max_self_play_steps=2_000,
    )
    b = run_self_play_game(
        game_id="det",
        player_count=2,
        strategies=[r.create("random"), r.create("random")],
        seed=42,
        max_turns=15,
        max_self_play_steps=2_000,
    )
    assert a.rankings == b.rankings
    assert a.ended_by == b.ended_by
    assert a.turns == b.turns
    assert a.self_play_steps == b.self_play_steps

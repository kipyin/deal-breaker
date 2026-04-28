"""Stable evaluation conventions for benchmarking neural policies vs baselines.

Callers rely on deterministic ``seed`` spacing (aligned with tournament: game *i*
uses ``seed + i``); max-turn stalemate semantics from ``run_self_play_game`` and
:class:`dbreaker.engine.game.Game`; and ``SELF_PLAY_STEP_LIMIT_STANDARD`` when
matching published tournament runs unless otherwise noted.
"""

from __future__ import annotations

EVAL_PROTOCOL_REVISION = "2026.04-eval-v1"

# Default match engine limits documented for gauntlets and regression suites.
DEFAULT_MAX_TURNS = 200
DEFAULT_MAX_SELF_PLAY_STEPS = 30_000

# Baselines used in champion selection and RL search promotions.
DEFAULT_GAUNTLET_BASELINES: tuple[str, ...] = (
    "basic",
    "aggressive",
    "defensive",
    "set_completion",
)

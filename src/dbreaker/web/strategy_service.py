from __future__ import annotations

from dbreaker.strategies.registry import default_registry


def list_strategies() -> dict[str, str | list[str]]:
    return {
        "built_in": default_registry().names(),
        "neural_prefix": "neural:",
        "hint": (
            "Use neural:<path_to_checkpoint.pt> relative to the artifact root, "
            "or an absolute path, for policy checkpoints."
        ),
    }

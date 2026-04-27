from __future__ import annotations

from pathlib import Path

from dbreaker.engine.actions import Action
from dbreaker.engine.observation import Observation
from dbreaker.ml.checkpoint import load_checkpoint
from dbreaker.ml.features import encode_legal_actions
from dbreaker.ml.model import PolicyValueNetwork, choose_action_index
from dbreaker.strategies.base import StrategyDecision


class NeuralStrategy:
    def __init__(self, checkpoint_path: Path, *, model: PolicyValueNetwork | None = None) -> None:
        self.checkpoint_path = checkpoint_path
        self.name = f"neural:{checkpoint_path}"
        self._model = model if model is not None else load_checkpoint(checkpoint_path).model

    def choose_action(
        self,
        observation: Observation,
        legal_actions: list[Action],
    ) -> StrategyDecision:
        if not legal_actions:
            raise ValueError("legal_actions cannot be empty")
        batch = encode_legal_actions(observation, legal_actions)
        selection = choose_action_index(self._model, batch, greedy=True)
        return StrategyDecision(
            action=legal_actions[selection.index],
            reason_summary=f"{self.name} selected legal action #{selection.index}.",
            debug_reasoning=f"value={selection.value:.3f} log_prob={selection.log_prob:.3f}",
        )

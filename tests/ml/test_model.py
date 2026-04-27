from __future__ import annotations

import pytest

from dbreaker.engine.game import Game
from dbreaker.ml.features import encode_legal_actions
from dbreaker.ml.model import PolicyValueNetwork, choose_action_index, evaluate_action_indices

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(torch is None, reason="torch is not installed")


def test_policy_model_scores_only_legal_candidates() -> None:
    game = Game.new(player_count=2, seed=2)
    batch = encode_legal_actions(game.observation_for("P1"), game.legal_actions("P1"))
    model = PolicyValueNetwork()

    output = model.forward_batch(batch)

    assert tuple(output.logits.shape) == (len(batch.actions),)
    assert tuple(output.value.shape) == ()


def test_action_sampling_and_evaluation_return_candidate_indices() -> None:
    torch.manual_seed(3)
    game = Game.new(player_count=2, seed=2)
    batch = encode_legal_actions(game.observation_for("P1"), game.legal_actions("P1"))
    model = PolicyValueNetwork()

    sampled = choose_action_index(model, batch, greedy=False)
    greedy = choose_action_index(model, batch, greedy=True)
    evaluated = evaluate_action_indices(model, [batch], torch.tensor([sampled.index]))

    assert 0 <= sampled.index < len(batch.actions)
    assert 0 <= greedy.index < len(batch.actions)
    assert tuple(evaluated.log_probs.shape) == (1,)
    assert tuple(evaluated.values.shape) == (1,)
    assert tuple(evaluated.entropies.shape) == (1,)

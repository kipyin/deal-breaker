from __future__ import annotations

import pytest

from dbreaker.engine.game import Game
from dbreaker.ml.features import (
    ACTION_FEATURE_DIM,
    FEATURE_SCHEMA_VERSION,
    OBSERVATION_FEATURE_DIM,
    EncodedActionBatch,
    encode_legal_actions,
)
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


def test_choose_action_index_can_skip_entropy_computation() -> None:
    torch.manual_seed(13)
    game = Game.new(player_count=2, seed=2)
    batch = encode_legal_actions(game.observation_for("P1"), game.legal_actions("P1"))
    model = PolicyValueNetwork()

    greedy_with_entropy = choose_action_index(model, batch, greedy=True)
    greedy_without_entropy = choose_action_index(
        model, batch, greedy=True, include_entropy=False
    )

    assert greedy_with_entropy.index == greedy_without_entropy.index
    assert greedy_with_entropy.log_prob == greedy_without_entropy.log_prob
    assert greedy_with_entropy.value == greedy_without_entropy.value
    assert greedy_without_entropy.entropy == 0.0


def test_evaluate_action_indices_chunked_matches_reference() -> None:
    torch.manual_seed(0)
    game = Game.new(player_count=2, seed=1)
    model = PolicyValueNetwork()
    batches: list = []
    indices: list[int] = []
    for _ in range(4):
        player_id = game.active_player_id
        legal = game.legal_actions(player_id)
        batch = encode_legal_actions(game.observation_for(player_id), legal)
        choice = choose_action_index(model, batch, greedy=True)
        batches.append(batch)
        indices.append(choice.index)
        game.step(player_id, legal[choice.index])

    idx_tensor = torch.tensor(indices, dtype=torch.long)
    chunked = evaluate_action_indices(model, batches, idx_tensor, chunk_size=2)

    ref_log_probs: list = []
    ref_values: list = []
    ref_entropies: list = []
    for batch, idx in zip(batches, indices, strict=True):
        output = model.forward_batch(batch)
        dist = torch.distributions.Categorical(logits=output.logits)
        idx_t = torch.tensor(idx, dtype=torch.long)
        ref_log_probs.append(dist.log_prob(idx_t))
        ref_values.append(output.value)
        ref_entropies.append(dist.entropy())

    torch.testing.assert_close(chunked.log_probs, torch.stack(ref_log_probs))
    torch.testing.assert_close(chunked.values, torch.stack(ref_values))
    torch.testing.assert_close(chunked.entropies, torch.stack(ref_entropies))


def test_evaluate_action_indices_handles_skewed_legal_action_counts() -> None:
    torch.manual_seed(7)
    model = PolicyValueNetwork()

    small_batch = EncodedActionBatch(
        schema_version=FEATURE_SCHEMA_VERSION,
        observation_features=(0.1,) * OBSERVATION_FEATURE_DIM,
        action_features=((0.2,) * ACTION_FEATURE_DIM,),
        actions=tuple(),
    )
    large_actions = tuple((float(i % 7) / 7.0,) * ACTION_FEATURE_DIM for i in range(1536))
    large_batch = EncodedActionBatch(
        schema_version=FEATURE_SCHEMA_VERSION,
        observation_features=(0.3,) * OBSERVATION_FEATURE_DIM,
        action_features=large_actions,
        actions=tuple(),
    )
    medium_actions = tuple((float(i % 5) / 5.0,) * ACTION_FEATURE_DIM for i in range(9))
    medium_batch = EncodedActionBatch(
        schema_version=FEATURE_SCHEMA_VERSION,
        observation_features=(0.4,) * OBSERVATION_FEATURE_DIM,
        action_features=medium_actions,
        actions=tuple(),
    )
    batches = [small_batch, large_batch, medium_batch]
    indices = [0, 1000, 5]
    idx_tensor = torch.tensor(indices, dtype=torch.long)

    evaluated = evaluate_action_indices(model, batches, idx_tensor, chunk_size=3)

    ref_log_probs: list = []
    ref_values: list = []
    ref_entropies: list = []
    for batch, idx in zip(batches, indices, strict=True):
        output = model.forward_batch(batch)
        dist = torch.distributions.Categorical(logits=output.logits)
        idx_t = torch.tensor(idx, dtype=torch.long)
        ref_log_probs.append(dist.log_prob(idx_t))
        ref_values.append(output.value)
        ref_entropies.append(dist.entropy())

    torch.testing.assert_close(evaluated.log_probs, torch.stack(ref_log_probs))
    torch.testing.assert_close(evaluated.values, torch.stack(ref_values))
    torch.testing.assert_close(evaluated.entropies, torch.stack(ref_entropies))

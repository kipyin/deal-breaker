from __future__ import annotations

from dbreaker.engine.game import Game
from dbreaker.ml.features import (
    ACTION_FEATURE_DIM,
    FEATURE_SCHEMA_VERSION,
    OBSERVATION_FEATURE_DIM,
    encode_action,
    encode_legal_actions,
    encode_observation,
)


def test_observation_features_are_deterministic_and_schema_versioned() -> None:
    game = Game.new(player_count=3, seed=7)
    observation = game.observation_for("P1")

    first = encode_observation(observation)
    second = encode_observation(observation)

    assert FEATURE_SCHEMA_VERSION == "dbreaker-ml-features-v1"
    assert first == second
    assert len(first) == OBSERVATION_FEATURE_DIM


def test_legal_action_batch_preserves_action_mapping() -> None:
    game = Game.new(player_count=2, seed=11)
    observation = game.observation_for("P1")
    legal_actions = game.legal_actions("P1")

    batch = encode_legal_actions(observation, legal_actions)

    assert batch.actions == tuple(legal_actions)
    assert batch.schema_version == FEATURE_SCHEMA_VERSION
    assert batch.observation_features == encode_observation(observation)
    assert len(batch.action_features) == len(legal_actions)
    assert all(len(features) == ACTION_FEATURE_DIM for features in batch.action_features)
    assert batch.action_features[0] == encode_action(observation, legal_actions[0])

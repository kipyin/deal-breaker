from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dbreaker.ml.features import (
    ACTION_FEATURE_DIM,
    OBSERVATION_FEATURE_DIM,
    EncodedActionBatch,
)

try:
    import torch
    from torch import nn
    from torch.distributions import Categorical
except ImportError:
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    Categorical = None  # type: ignore[assignment]


def require_torch() -> Any:
    if torch is None or nn is None or Categorical is None:
        raise ImportError(
            "Install ML dependencies with `pip install dbreaker[ml]` to use neural AI."
        )
    return torch


@dataclass(frozen=True, slots=True)
class PolicyOutput:
    logits: Any
    value: Any


@dataclass(frozen=True, slots=True)
class ActionSelection:
    index: int
    log_prob: float
    value: float
    entropy: float


@dataclass(frozen=True, slots=True)
class EvaluationOutput:
    log_probs: Any
    values: Any
    entropies: Any


if nn is not None:

    class PolicyValueNetwork(nn.Module):  # type: ignore[misc]
        def __init__(
            self,
            observation_dim: int = OBSERVATION_FEATURE_DIM,
            action_dim: int = ACTION_FEATURE_DIM,
            hidden_dim: int = 64,
        ) -> None:
            super().__init__()
            self.observation_dim = observation_dim
            self.action_dim = action_dim
            self.hidden_dim = hidden_dim
            self.observation_encoder = nn.Sequential(
                nn.Linear(observation_dim, hidden_dim),
                nn.Tanh(),
            )
            self.action_encoder = nn.Sequential(
                nn.Linear(action_dim, hidden_dim),
                nn.Tanh(),
            )
            self.policy_head = nn.Sequential(
                nn.Linear(hidden_dim * 2, hidden_dim),
                nn.Tanh(),
                nn.Linear(hidden_dim, 1),
            )
            self.value_head = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim),
                nn.Tanh(),
                nn.Linear(hidden_dim, 1),
            )

        def forward_batch(self, batch: EncodedActionBatch) -> PolicyOutput:
            require_torch()
            obs = torch.tensor(batch.observation_features, dtype=torch.float32)
            action_features = torch.tensor(batch.action_features, dtype=torch.float32)
            obs_hidden = self.observation_encoder(obs)
            action_hidden = self.action_encoder(action_features)
            expanded_obs = obs_hidden.expand(action_hidden.shape[0], -1)
            logits = self.policy_head(torch.cat([expanded_obs, action_hidden], dim=1)).squeeze(-1)
            value = self.value_head(obs_hidden).squeeze(-1)
            return PolicyOutput(logits=logits, value=value)

        def model_config(self) -> dict[str, int]:
            return {
                "observation_dim": self.observation_dim,
                "action_dim": self.action_dim,
                "hidden_dim": self.hidden_dim,
            }

else:

    class PolicyValueNetwork:  # type: ignore[no-redef]
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            require_torch()


def choose_action_index(
    model: PolicyValueNetwork,
    batch: EncodedActionBatch,
    *,
    greedy: bool = False,
) -> ActionSelection:
    require_torch()
    output = model.forward_batch(batch)
    distribution = Categorical(logits=output.logits)
    if greedy:
        index_tensor = torch.argmax(output.logits)
    else:
        index_tensor = distribution.sample()
    log_prob = distribution.log_prob(index_tensor)
    return ActionSelection(
        index=int(index_tensor.item()),
        log_prob=float(log_prob.detach().item()),
        value=float(output.value.detach().item()),
        entropy=float(distribution.entropy().detach().item()),
    )


def evaluate_action_indices(
    model: PolicyValueNetwork,
    batches: list[EncodedActionBatch],
    action_indices: Any,
) -> EvaluationOutput:
    require_torch()
    log_probs = []
    values = []
    entropies = []
    for batch, action_index in zip(batches, action_indices, strict=True):
        output = model.forward_batch(batch)
        distribution = Categorical(logits=output.logits)
        log_probs.append(distribution.log_prob(action_index))
        values.append(output.value)
        entropies.append(distribution.entropy())
    return EvaluationOutput(
        log_probs=torch.stack(log_probs),
        values=torch.stack(values),
        entropies=torch.stack(entropies),
    )

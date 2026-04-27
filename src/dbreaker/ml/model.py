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
            hidden_dim: int = 128,
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

        def forward_batch_padded(
            self,
            observation_rows: Any,
            action_rows: Any,
            valid_mask: Any,
        ) -> PolicyOutput:
            """Vectorized forward for a chunk of states with different legal-action counts.

            ``observation_rows`` is ``[B, observation_dim]``; ``action_rows`` is
            ``[B, max_actions, action_dim]``; ``valid_mask`` is ``[B, max_actions]``
            with True for real legal slots (padded slots must be False).
            """
            require_torch()
            obs_hidden = self.observation_encoder(observation_rows)
            batch_size, max_actions, _ = action_rows.shape
            flat_actions = action_rows.reshape(batch_size * max_actions, self.action_dim)
            action_hidden = self.action_encoder(flat_actions).reshape(
                batch_size, max_actions, self.hidden_dim
            )
            expanded_obs = obs_hidden.unsqueeze(1).expand(-1, max_actions, -1)
            combined = torch.cat([expanded_obs, action_hidden], dim=-1)
            logits = (
                self.policy_head(combined.reshape(batch_size * max_actions, self.hidden_dim * 2))
                .view(batch_size, max_actions)
                .squeeze(-1)
            )
            logits = logits.masked_fill(~valid_mask, -1e9)
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
    *,
    chunk_size: int = 256,
) -> EvaluationOutput:
    require_torch()
    if not batches:
        return EvaluationOutput(
            log_probs=torch.tensor([], dtype=torch.float32),
            values=torch.tensor([], dtype=torch.float32),
            entropies=torch.tensor([], dtype=torch.float32),
        )
    device = next(model.parameters()).device
    log_prob_chunks: list[Any] = []
    value_chunks: list[Any] = []
    entropy_chunks: list[Any] = []
    action_indices = action_indices.to(device=device, dtype=torch.long)
    for start in range(0, len(batches), chunk_size):
        end = min(start + chunk_size, len(batches))
        chunk_batches = batches[start:end]
        chunk_idx = action_indices[start:end]
        batch_len = len(chunk_batches)
        max_actions = max(len(b.action_features) for b in chunk_batches)
        obs_tensor = torch.zeros(
            batch_len,
            model.observation_dim,
            dtype=torch.float32,
            device=device,
        )
        action_tensor = torch.zeros(
            batch_len,
            max_actions,
            model.action_dim,
            dtype=torch.float32,
            device=device,
        )
        mask = torch.zeros(batch_len, max_actions, dtype=torch.bool, device=device)
        for row, batch in enumerate(chunk_batches):
            legal_n = len(batch.action_features)
            obs_tensor[row] = torch.tensor(
                batch.observation_features, dtype=torch.float32, device=device
            )
            if legal_n:
                action_tensor[row, :legal_n] = torch.tensor(
                    batch.action_features, dtype=torch.float32, device=device
                )
                mask[row, :legal_n] = True
        output = model.forward_batch_padded(obs_tensor, action_tensor, mask)
        distribution = Categorical(logits=output.logits)
        log_prob_chunks.append(distribution.log_prob(chunk_idx))
        value_chunks.append(output.value)
        entropy_chunks.append(distribution.entropy())
    return EvaluationOutput(
        log_probs=torch.cat(log_prob_chunks),
        values=torch.cat(value_chunks),
        entropies=torch.cat(entropy_chunks),
    )

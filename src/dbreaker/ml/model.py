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


def resolve_training_device(torch_mod: Any, choice: str = "auto") -> Any:
    """Pick PyTorch device: Apple Silicon Metal ``mps``, NVIDIA ``cuda``, or ``cpu``.

    ``choice`` is ``auto`` | ``cpu`` | ``mps`` | ``cuda`` (synonym ``gpu`` for cuda).
    """
    c = (choice or "auto").lower().strip()
    if c == "cpu":
        return torch_mod.device("cpu")
    if c == "mps":
        if not torch_mod.backends.mps.is_available():
            raise ValueError("device=mps requested but MPS is not available")
        return torch_mod.device("mps")
    if c in ("cuda", "gpu"):
        if not torch_mod.cuda.is_available():
            raise ValueError("device=cuda requested but CUDA is not available")
        return torch_mod.device("cuda")
    if c != "auto":
        raise ValueError(f"unsupported device choice: {choice!r}")
    if torch_mod.backends.mps.is_available():
        return torch_mod.device("mps")
    if torch_mod.cuda.is_available():
        return torch_mod.device("cuda")
    return torch_mod.device("cpu")


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
    policy_topk_indices: tuple[int, ...] = ()
    policy_topk_probs: tuple[float, ...] = ()


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
            device = next(self.parameters()).device
            obs = torch.tensor(batch.observation_features, dtype=torch.float32, device=device)
            action_features = torch.tensor(
                batch.action_features,
                dtype=torch.float32,
                device=device,
            )
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

        def model_config(self) -> dict[str, Any]:
            return {
                "kind": "mlp",
                "observation_dim": self.observation_dim,
                "action_dim": self.action_dim,
                "hidden_dim": self.hidden_dim,
            }

    class StructuredPolicyValueNetwork(nn.Module):  # type: ignore[misc]
        """Deeper residual observation tower on top of the same featureization."""

        def __init__(
            self,
            observation_dim: int = OBSERVATION_FEATURE_DIM,
            action_dim: int = ACTION_FEATURE_DIM,
            hidden_dim: int = 128,
            residual_layers: int = 2,
        ) -> None:
            super().__init__()
            self.observation_dim = observation_dim
            self.action_dim = action_dim
            self.hidden_dim = hidden_dim
            self.observation_encoder = nn.Sequential(
                nn.Linear(observation_dim, hidden_dim),
                nn.Tanh(),
            )
            self.observation_residual = nn.ModuleList(
                nn.Sequential(
                    nn.Linear(hidden_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Linear(hidden_dim, hidden_dim),
                    nn.Tanh(),
                )
                for _ in range(residual_layers)
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
            device = next(self.parameters()).device
            obs = torch.tensor(batch.observation_features, dtype=torch.float32, device=device)
            action_features = torch.tensor(
                batch.action_features,
                dtype=torch.float32,
                device=device,
            )
            obs_hidden = self.observation_encoder(obs)
            for block in self.observation_residual:
                obs_hidden = obs_hidden + block(obs_hidden)
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
            require_torch()
            obs_hidden = self.observation_encoder(observation_rows)
            for block in self.observation_residual:
                obs_hidden = obs_hidden + block(obs_hidden)
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

        def model_config(self) -> dict[str, Any]:
            return {
                "kind": "structured",
                "observation_dim": self.observation_dim,
                "action_dim": self.action_dim,
                "hidden_dim": self.hidden_dim,
                "residual_layers": len(self.observation_residual),
            }

else:

    class PolicyValueNetwork:  # type: ignore[no-redef]
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            require_torch()

    class StructuredPolicyValueNetwork(PolicyValueNetwork):  # type: ignore[no-redef]
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            require_torch()


def build_policy_from_config(payload: dict[str, Any]) -> Any:
    """Instantiate checkpoint-compatible policy nets (backward compatible defaults)."""
    require_torch()
    kind = payload.get("kind", "mlp")
    observation_dim = int(payload["observation_dim"])
    action_dim = int(payload["action_dim"])
    hidden_dim = int(payload.get("hidden_dim", 128))
    if kind == "structured":
        residual_layers = int(payload.get("residual_layers", 2))
        return StructuredPolicyValueNetwork(
            observation_dim=observation_dim,
            action_dim=action_dim,
            hidden_dim=hidden_dim,
            residual_layers=residual_layers,
        )
    return PolicyValueNetwork(
        observation_dim=observation_dim,
        action_dim=action_dim,
        hidden_dim=hidden_dim,
    )


def top_k_action_scores(
    model: Any,
    batch: EncodedActionBatch,
    *,
    k: int,
) -> list[tuple[int, float]]:
    """Return up to ``k`` (index, logit) pairs sorted by descending logit."""
    require_torch()
    output = model.forward_batch(batch)
    logits_cpu = output.logits.detach().float().cpu()
    pairs = sorted(
        enumerate(float(x) for x in logits_cpu.tolist()),
        key=lambda pair: (-pair[1], pair[0]),
    )
    return pairs[: max(0, k)]


def choose_action_index(
    model: Any,
    batch: EncodedActionBatch,
    *,
    greedy: bool = False,
    include_entropy: bool = True,
    top_k: int | None = None,
) -> ActionSelection:
    """Sample or greedy-argmax one legal action; optional softmax top-k counterfactual probs."""
    require_torch()
    output = model.forward_batch(batch)
    distribution = Categorical(logits=output.logits)
    if greedy:
        index_tensor = torch.argmax(output.logits)
    else:
        index_tensor = distribution.sample()
    log_prob = distribution.log_prob(index_tensor)
    entropy = distribution.entropy() if include_entropy else None
    top_idx: tuple[int, ...] = ()
    top_p: tuple[float, ...] = ()
    if top_k is not None and top_k > 0:
        probs = torch.softmax(output.logits, dim=-1)
        kk = min(top_k, int(probs.numel()))
        vals, idx = torch.topk(probs, k=kk)
        top_idx = tuple(int(i) for i in idx.tolist())
        top_p = tuple(float(v) for v in vals.tolist())
    return ActionSelection(
        index=int(index_tensor.item()),
        log_prob=float(log_prob.detach().item()),
        value=float(output.value.detach().item()),
        entropy=float(entropy.detach().item()) if entropy is not None else 0.0,
        policy_topk_indices=top_idx,
        policy_topk_probs=top_p,
    )


def evaluation_forward_chunk_size(device: Any) -> int:
    """Chunk size for padded policy eval; MPS unified memory is easy to exhaust."""
    if device.type == "mps":
        return 24
    if device.type == "cuda":
        return 128
    return 256


def evaluate_action_indices(
    model: Any,
    batches: list[EncodedActionBatch],
    action_indices: Any,
    *,
    chunk_size: int | None = None,
) -> EvaluationOutput:
    require_torch()
    if not batches:
        return EvaluationOutput(
            log_probs=torch.tensor([], dtype=torch.float32),
            values=torch.tensor([], dtype=torch.float32),
            entropies=torch.tensor([], dtype=torch.float32),
        )
    device = next(model.parameters()).device
    if chunk_size is None:
        chunk_size = evaluation_forward_chunk_size(device)
    log_prob_chunks: list[Any] = []
    value_chunks: list[Any] = []
    entropy_chunks: list[Any] = []
    action_indices = action_indices.to(device=device, dtype=torch.long)
    for start in range(0, len(batches), chunk_size):
        end = min(start + chunk_size, len(batches))
        chunk_batches = batches[start:end]
        chunk_idx = action_indices[start:end]
        action_counts = [len(batch.action_features) for batch in chunk_batches]
        if any(count == 0 for count in action_counts):
            raise ValueError("each EncodedActionBatch must include at least one legal action")

        state_obs_tensor = torch.tensor(
            [batch.observation_features for batch in chunk_batches],
            dtype=torch.float32,
            device=device,
        )
        state_obs_hidden = model.observation_encoder(state_obs_tensor)
        value_chunks.append(model.value_head(state_obs_hidden).squeeze(-1))

        flat_action_features = [
            action_feature
            for batch in chunk_batches
            for action_feature in batch.action_features
        ]
        action_tensor = torch.tensor(
            flat_action_features,
            dtype=torch.float32,
            device=device,
        )
        action_hidden = model.action_encoder(action_tensor)
        counts_tensor = torch.tensor(action_counts, dtype=torch.long, device=device)
        repeated_obs_hidden = torch.repeat_interleave(state_obs_hidden, counts_tensor, dim=0)
        flat_logits = model.policy_head(
            torch.cat([repeated_obs_hidden, action_hidden], dim=1)
        ).squeeze(-1)

        state_log_probs: list[Any] = []
        state_entropies: list[Any] = []
        offset = 0
        for row, legal_count in enumerate(action_counts):
            row_logits = flat_logits[offset : offset + legal_count]
            row_distribution = Categorical(logits=row_logits)
            row_index = chunk_idx[row]
            state_log_probs.append(row_distribution.log_prob(row_index))
            state_entropies.append(row_distribution.entropy())
            offset += legal_count
        log_prob_chunks.append(torch.stack(state_log_probs))
        entropy_chunks.append(torch.stack(state_entropies))
    return EvaluationOutput(
        log_probs=torch.cat(log_prob_chunks),
        values=torch.cat(value_chunks),
        entropies=torch.cat(entropy_chunks),
    )

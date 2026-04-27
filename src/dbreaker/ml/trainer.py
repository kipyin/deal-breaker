from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dbreaker.ml.checkpoint import save_checkpoint
from dbreaker.ml.model import PolicyValueNetwork, evaluate_action_indices, require_torch
from dbreaker.ml.trajectory import (
    collect_training_trajectory,
    sparse_terminal_rewards_for_steps,
)


@dataclass(frozen=True, slots=True)
class PPOConfig:
    games: int = 10
    player_count: int = 4
    max_turns: int = 200
    max_self_play_steps: int = 30_000
    learning_rate: float = 3e-4
    clip_epsilon: float = 0.2
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    update_epochs: int = 2
    gamma: float = 0.99
    opponent_mix_prob: float = 0.0
    opponent_strategies: tuple[str, ...] = (
        "basic",
        "aggressive",
        "defensive",
        "set_completion",
    )
    champion_checkpoint: Path | None = None


@dataclass(frozen=True, slots=True)
class TrainingStats:
    games: int
    steps: int
    mean_reward: float
    checkpoint_path: str | None
    mean_entropy: float | None = None

    def as_dict(self) -> dict[str, int | float | str | None]:
        payload: dict[str, int | float | str | None] = {
            "games": self.games,
            "steps": self.steps,
            "mean_reward": self.mean_reward,
            "checkpoint_path": self.checkpoint_path,
        }
        if self.mean_entropy is not None:
            payload["mean_entropy"] = self.mean_entropy
        return payload


@dataclass
class SelfPlayPhaseTimings:
    """Wall-clock breakdown for :func:`train_self_play` (mutable; optional out-parameter)."""

    rollout_seconds: float = 0.0
    ppo_update_seconds: float = 0.0
    total_seconds: float = 0.0
    mean_legal_actions_per_step: float = 0.0
    training_steps: int = 0


def _discounted_returns(rewards: Any, gamma: float, torch: Any) -> Any:
    n = int(rewards.shape[0])
    if n == 0:
        return rewards
    returns = torch.zeros_like(rewards)
    returns[-1] = rewards[-1]
    for t in range(n - 2, -1, -1):
        returns[t] = rewards[t] + gamma * returns[t + 1]
    return returns


def train_self_play(
    config: PPOConfig,
    *,
    checkpoint_out: Path | None = None,
    seed: int | None = None,
    model: PolicyValueNetwork | None = None,
    phase_timings: SelfPlayPhaseTimings | None = None,
    torch_seed: int | None = None,
) -> TrainingStats:
    torch = require_torch()
    if torch_seed is not None:
        torch.manual_seed(torch_seed)
    policy = model or PolicyValueNetwork()
    optimizer = torch.optim.Adam(policy.parameters(), lr=config.learning_rate)
    total_t0 = time.perf_counter()
    rollout_t0 = time.perf_counter()
    trajectories = [
        collect_training_trajectory(
            policy,
            player_count=config.player_count,
            seed=None if seed is None else seed + game_index,
            max_turns=config.max_turns,
            max_self_play_steps=config.max_self_play_steps,
            opponent_mix_prob=config.opponent_mix_prob,
            opponent_strategies=config.opponent_strategies,
            champion_checkpoint=config.champion_checkpoint,
        )
        for game_index in range(config.games)
    ]
    rollout_seconds = time.perf_counter() - rollout_t0
    steps = [step for trajectory in trajectories for step in trajectory.steps]
    rewards_dense = [reward for trajectory in trajectories for reward in trajectory.rewards]
    sparse_parts: list[float] = []
    for trajectory in trajectories:
        reward_by_player = {
            step.player_id: reward
            for step, reward in zip(trajectory.steps, trajectory.rewards, strict=True)
        }
        sparse_parts.extend(
            sparse_terminal_rewards_for_steps(trajectory.steps, reward_by_player)
        )
    mean_entropy: float | None = None
    ppo_t0 = time.perf_counter()
    if steps:
        old_log_probs = torch.tensor([step.log_prob for step in steps], dtype=torch.float32)
        old_values = torch.tensor([step.value for step in steps], dtype=torch.float32)
        sparse_rewards = torch.tensor(sparse_parts, dtype=torch.float32)
        returns = _discounted_returns(sparse_rewards, config.gamma, torch)
        advantages = returns - old_values.detach()
        adv_std = advantages.std(unbiased=False)
        if adv_std > 1e-8:
            advantages = (advantages - advantages.mean()) / (adv_std + 1e-8)
        action_indices = torch.tensor(
            [step.action_index for step in steps],
            dtype=torch.long,
        )
        batches = [step.batch for step in steps]
        for _ in range(config.update_epochs):
            evaluated = evaluate_action_indices(policy, batches, action_indices)
            ratios = torch.exp(evaluated.log_probs - old_log_probs)
            clipped = torch.clamp(
                ratios,
                1.0 - config.clip_epsilon,
                1.0 + config.clip_epsilon,
            )
            policy_loss = -torch.min(ratios * advantages, clipped * advantages).mean()
            value_loss = torch.nn.functional.mse_loss(evaluated.values, returns)
            entropy_bonus = evaluated.entropies.mean()
            mean_entropy = float(entropy_bonus.detach().item())
            loss = (
                policy_loss
                + config.value_coef * value_loss
                - config.entropy_coef * entropy_bonus
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    ppo_update_seconds = time.perf_counter() - ppo_t0
    mean_reward = sum(rewards_dense) / len(rewards_dense) if rewards_dense else 0.0
    stats = TrainingStats(
        games=config.games,
        steps=len(steps),
        mean_reward=mean_reward,
        checkpoint_path=str(checkpoint_out) if checkpoint_out is not None else None,
        mean_entropy=mean_entropy,
    )
    if checkpoint_out is not None:
        save_checkpoint(checkpoint_out, model=policy, training_stats=stats.as_dict())
    total_seconds = time.perf_counter() - total_t0
    if phase_timings is not None:
        legal_sum = 0
        for trajectory in trajectories:
            for step in trajectory.steps:
                legal_sum += len(step.batch.actions)
        n_steps = len(steps)
        phase_timings.rollout_seconds = rollout_seconds
        phase_timings.ppo_update_seconds = ppo_update_seconds
        phase_timings.total_seconds = total_seconds
        phase_timings.training_steps = n_steps
        phase_timings.mean_legal_actions_per_step = (
            float(legal_sum) / float(n_steps) if n_steps else 0.0
        )
    return stats

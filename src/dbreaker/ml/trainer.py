from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dbreaker.ml.checkpoint import load_checkpoint, save_checkpoint
from dbreaker.ml.model import PolicyValueNetwork, evaluate_action_indices, require_torch
from dbreaker.ml.trajectory import (
    SelfPlayTrajectory,
    collect_training_trajectory,
    sparse_terminal_rewards_for_steps,
)

TrajectoryProgress = Callable[[int, SelfPlayTrajectory], None]


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
    policy_loss: float | None = None
    value_loss: float | None = None
    total_loss: float | None = None
    clip_fraction: float | None = None
    rollout_seconds: float | None = None
    ppo_update_seconds: float | None = None
    total_seconds: float | None = None
    mean_legal_actions_per_step: float | None = None
    ended_by: dict[str, int] | None = None
    learner_steps_mean: float | None = None
    learner_steps_max: int | None = None
    mean_reward_per_game_min: float | None = None
    mean_reward_per_game_max: float | None = None
    per_game: tuple[dict[str, Any], ...] | None = None
    continued_from: str | None = None
    game_seed_offset: int = 0

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "games": self.games,
            "steps": self.steps,
            "mean_reward": self.mean_reward,
            "checkpoint_path": self.checkpoint_path,
            "game_seed_offset": self.game_seed_offset,
        }
        if self.continued_from is not None:
            payload["continued_from"] = self.continued_from
        if self.mean_entropy is not None:
            payload["mean_entropy"] = self.mean_entropy
        if self.policy_loss is not None:
            payload["policy_loss"] = self.policy_loss
        if self.value_loss is not None:
            payload["value_loss"] = self.value_loss
        if self.total_loss is not None:
            payload["total_loss"] = self.total_loss
        if self.clip_fraction is not None:
            payload["clip_fraction"] = self.clip_fraction
        if self.rollout_seconds is not None:
            payload["rollout_seconds"] = self.rollout_seconds
        if self.ppo_update_seconds is not None:
            payload["ppo_update_seconds"] = self.ppo_update_seconds
        if self.total_seconds is not None:
            payload["total_seconds"] = self.total_seconds
        if self.mean_legal_actions_per_step is not None:
            payload["mean_legal_actions_per_step"] = self.mean_legal_actions_per_step
        if self.ended_by is not None:
            payload["ended_by"] = dict(self.ended_by)
        if self.learner_steps_mean is not None:
            payload["learner_steps_mean"] = self.learner_steps_mean
        if self.learner_steps_max is not None:
            payload["learner_steps_max"] = self.learner_steps_max
        if self.mean_reward_per_game_min is not None:
            payload["mean_reward_per_game_min"] = self.mean_reward_per_game_min
        if self.mean_reward_per_game_max is not None:
            payload["mean_reward_per_game_max"] = self.mean_reward_per_game_max
        if self.per_game is not None:
            payload["per_game"] = [dict(row) for row in self.per_game]
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


def _mean_reward_for_trajectory(trajectory: SelfPlayTrajectory) -> float:
    if not trajectory.rewards:
        return 0.0
    return float(sum(trajectory.rewards) / len(trajectory.rewards))


def train_self_play(
    config: PPOConfig,
    *,
    checkpoint_out: Path | None = None,
    seed: int | None = None,
    model: PolicyValueNetwork | None = None,
    from_checkpoint: Path | None = None,
    game_seed_offset: int = 0,
    phase_timings: SelfPlayPhaseTimings | None = None,
    torch_seed: int | None = None,
    on_game_complete: TrajectoryProgress | None = None,
    metrics_out: Path | None = None,
) -> TrainingStats:
    if model is not None and from_checkpoint is not None:
        raise ValueError("pass at most one of model= and from_checkpoint=")
    torch = require_torch()
    if torch_seed is not None:
        torch.manual_seed(torch_seed)
    continued_from: str | None = None
    if from_checkpoint is not None:
        policy = load_checkpoint(from_checkpoint).model
        continued_from = str(from_checkpoint)
    elif model is not None:
        policy = model
    else:
        policy = PolicyValueNetwork()
    policy.train()
    optimizer = torch.optim.Adam(policy.parameters(), lr=config.learning_rate)
    total_t0 = time.perf_counter()
    rollout_t0 = time.perf_counter()
    trajectories: list[SelfPlayTrajectory] = []
    for game_index in range(config.games):
        trajectory = collect_training_trajectory(
            policy,
            player_count=config.player_count,
            seed=None
            if seed is None
            else seed + game_index + game_seed_offset,
            max_turns=config.max_turns,
            max_self_play_steps=config.max_self_play_steps,
            opponent_mix_prob=config.opponent_mix_prob,
            opponent_strategies=config.opponent_strategies,
            champion_checkpoint=config.champion_checkpoint,
        )
        trajectories.append(trajectory)
        if on_game_complete is not None:
            on_game_complete(game_index, trajectory)
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
    policy_loss_f: float | None = None
    value_loss_f: float | None = None
    total_loss_f: float | None = None
    clip_fraction_f: float | None = None
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
            clip_fraction = torch.mean(
                (torch.abs(ratios - 1.0) > config.clip_epsilon).float()
            )
            loss = (
                policy_loss
                + config.value_coef * value_loss
                - config.entropy_coef * entropy_bonus
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            policy_loss_f = float(policy_loss.detach().item())
            value_loss_f = float(value_loss.detach().item())
            total_loss_f = float(loss.detach().item())
            clip_fraction_f = float(clip_fraction.detach().item())
    ppo_update_seconds = time.perf_counter() - ppo_t0
    mean_reward = sum(rewards_dense) / len(rewards_dense) if rewards_dense else 0.0
    total_seconds = time.perf_counter() - total_t0

    legal_sum = 0
    for trajectory in trajectories:
        for step in trajectory.steps:
            legal_sum += len(step.batch.actions)
    n_steps = len(steps)
    mean_legal = float(legal_sum) / float(n_steps) if n_steps else 0.0

    ended_counts = Counter(t.ended_by for t in trajectories)
    lengths = [len(t.steps) for t in trajectories]
    mr_per_game = [_mean_reward_for_trajectory(t) for t in trajectories]
    learner_mean = float(sum(lengths) / len(lengths)) if lengths else 0.0
    learner_max = max(lengths) if lengths else 0
    mr_min = min(mr_per_game) if mr_per_game else 0.0
    mr_max = max(mr_per_game) if mr_per_game else 0.0
    per_game_rows: tuple[dict[str, Any], ...] = tuple(
        {
            "game_index": i,
            "learner_steps": len(traj.steps),
            "ended_by": traj.ended_by,
            "mean_reward": _mean_reward_for_trajectory(traj),
        }
        for i, traj in enumerate(trajectories)
    )

    stats = TrainingStats(
        games=config.games,
        steps=len(steps),
        mean_reward=mean_reward,
        checkpoint_path=str(checkpoint_out) if checkpoint_out is not None else None,
        mean_entropy=mean_entropy,
        policy_loss=policy_loss_f,
        value_loss=value_loss_f,
        total_loss=total_loss_f,
        clip_fraction=clip_fraction_f,
        rollout_seconds=rollout_seconds,
        ppo_update_seconds=ppo_update_seconds,
        total_seconds=total_seconds,
        mean_legal_actions_per_step=mean_legal,
        ended_by=dict(ended_counts),
        learner_steps_mean=learner_mean,
        learner_steps_max=learner_max,
        mean_reward_per_game_min=mr_min,
        mean_reward_per_game_max=mr_max,
        per_game=per_game_rows,
        continued_from=continued_from,
        game_seed_offset=game_seed_offset,
    )
    if checkpoint_out is not None:
        save_checkpoint(checkpoint_out, model=policy, training_stats=stats.as_dict())
    if phase_timings is not None:
        phase_timings.rollout_seconds = rollout_seconds
        phase_timings.ppo_update_seconds = ppo_update_seconds
        phase_timings.total_seconds = total_seconds
        phase_timings.training_steps = n_steps
        phase_timings.mean_legal_actions_per_step = mean_legal
    if metrics_out is not None:
        metrics_out.parent.mkdir(parents=True, exist_ok=True)
        metrics_out.write_text(
            json.dumps(stats.as_dict(), indent=2),
            encoding="utf-8",
        )
    return stats

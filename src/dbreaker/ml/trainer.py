from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dbreaker.ml.checkpoint import save_checkpoint
from dbreaker.ml.model import PolicyValueNetwork, evaluate_action_indices, require_torch
from dbreaker.ml.trajectory import collect_self_play_trajectory


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


@dataclass(frozen=True, slots=True)
class TrainingStats:
    games: int
    steps: int
    mean_reward: float
    checkpoint_path: str | None

    def as_dict(self) -> dict[str, int | float | str | None]:
        return {
            "games": self.games,
            "steps": self.steps,
            "mean_reward": self.mean_reward,
            "checkpoint_path": self.checkpoint_path,
        }


def train_self_play(
    config: PPOConfig,
    *,
    checkpoint_out: Path | None = None,
    seed: int | None = None,
    model: PolicyValueNetwork | None = None,
) -> TrainingStats:
    torch = require_torch()
    policy = model or PolicyValueNetwork()
    optimizer = torch.optim.Adam(policy.parameters(), lr=config.learning_rate)
    trajectories = [
        collect_self_play_trajectory(
            policy,
            player_count=config.player_count,
            seed=None if seed is None else seed + game_index,
            max_turns=config.max_turns,
            max_self_play_steps=config.max_self_play_steps,
        )
        for game_index in range(config.games)
    ]
    steps = [step for trajectory in trajectories for step in trajectory.steps]
    rewards = [reward for trajectory in trajectories for reward in trajectory.rewards]
    if steps:
        old_log_probs = torch.tensor([step.log_prob for step in steps], dtype=torch.float32)
        returns = torch.tensor(rewards, dtype=torch.float32)
        action_indices = torch.tensor([step.action_index for step in steps])
        batches = [step.batch for step in steps]
        for _ in range(config.update_epochs):
            evaluated = evaluate_action_indices(policy, batches, action_indices)
            advantages = returns - evaluated.values.detach()
            ratios = torch.exp(evaluated.log_probs - old_log_probs)
            clipped = torch.clamp(
                ratios,
                1.0 - config.clip_epsilon,
                1.0 + config.clip_epsilon,
            )
            policy_loss = -torch.min(ratios * advantages, clipped * advantages).mean()
            value_loss = torch.nn.functional.mse_loss(evaluated.values, returns)
            entropy_bonus = evaluated.entropies.mean()
            loss = (
                policy_loss
                + config.value_coef * value_loss
                - config.entropy_coef * entropy_bonus
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    mean_reward = sum(rewards) / len(rewards) if rewards else 0.0
    stats = TrainingStats(
        games=config.games,
        steps=len(steps),
        mean_reward=mean_reward,
        checkpoint_path=str(checkpoint_out) if checkpoint_out is not None else None,
    )
    if checkpoint_out is not None:
        save_checkpoint(checkpoint_out, model=policy, training_stats=stats.as_dict())
    return stats

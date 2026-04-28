from __future__ import annotations

import dataclasses
import json
import multiprocessing as mp
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dbreaker.ml.checkpoint import LoadedCheckpoint, load_checkpoint, save_checkpoint
from dbreaker.ml.model import (
    PolicyValueNetwork,
    StructuredPolicyValueNetwork,
    build_policy_from_config,
    evaluate_action_indices,
    evaluation_forward_chunk_size,
    require_torch,
    resolve_training_device,
)
from dbreaker.ml.trajectory import (
    SelfPlayTrajectory,
    collect_training_trajectory,
    sparse_terminal_rewards_for_steps,
)

TrajectoryProgress = Callable[[int, SelfPlayTrajectory], None]


@dataclass(frozen=True, slots=True)
class PPOConfig:
    games: int = 10
    rollout_batch_games: int = 500
    rollout_target_steps: int | None = None
    min_rollout_games: int = 1
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
    fast_single_learner: bool = False
    rollout_max_steps_per_game: int | None = None
    max_policy_actions: int | None = None
    policy_top_k: int | None = 3
    rollout_workers: int = 1


@dataclass(frozen=True, slots=True)
class TrainingStats:
    games: int
    steps: int
    mean_reward: float
    checkpoint_path: str | None
    rollout_batch_games: int = 500
    rollout_target_steps: int | None = None
    min_rollout_games: int = 1
    fast_single_learner: bool = False
    rollout_max_steps_per_game: int | None = None
    max_policy_actions: int | None = None
    ppo_updates: int = 0
    rollout_steps_per_update: tuple[int, ...] = ()
    mean_entropy: float | None = None
    policy_loss: float | None = None
    value_loss: float | None = None
    total_loss: float | None = None
    clip_fraction: float | None = None
    rollout_seconds: float | None = None
    ppo_update_seconds: float | None = None
    total_seconds: float | None = None
    mean_legal_actions_per_step: float | None = None
    max_legal_actions_per_step: int | None = None
    ended_by: dict[str, int] | None = None
    learner_steps_mean: float | None = None
    learner_steps_max: int | None = None
    truncated_games: int = 0
    candidate_actions_before: int = 0
    candidate_actions_after: int = 0
    candidate_actions_pruned: int = 0
    mean_candidate_actions_before: float | None = None
    mean_candidate_actions_after: float | None = None
    mean_reward_per_game_min: float | None = None
    mean_reward_per_game_max: float | None = None
    per_game: tuple[dict[str, Any], ...] | None = None
    continued_from: str | None = None
    game_seed_offset: int = 0
    training_device: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "games": self.games,
            "steps": self.steps,
            "mean_reward": self.mean_reward,
            "checkpoint_path": self.checkpoint_path,
            "game_seed_offset": self.game_seed_offset,
            "rollout_batch_games": self.rollout_batch_games,
            "min_rollout_games": self.min_rollout_games,
            "fast_single_learner": self.fast_single_learner,
            "ppo_updates": self.ppo_updates,
            "rollout_steps_per_update": list(self.rollout_steps_per_update),
            "truncated_games": self.truncated_games,
            "candidate_actions_before": self.candidate_actions_before,
            "candidate_actions_after": self.candidate_actions_after,
            "candidate_actions_pruned": self.candidate_actions_pruned,
        }
        if self.rollout_target_steps is not None:
            payload["rollout_target_steps"] = self.rollout_target_steps
        if self.rollout_max_steps_per_game is not None:
            payload["rollout_max_steps_per_game"] = self.rollout_max_steps_per_game
        if self.max_policy_actions is not None:
            payload["max_policy_actions"] = self.max_policy_actions
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
        if self.max_legal_actions_per_step is not None:
            payload["max_legal_actions_per_step"] = self.max_legal_actions_per_step
        if self.ended_by is not None:
            payload["ended_by"] = dict(self.ended_by)
        if self.learner_steps_mean is not None:
            payload["learner_steps_mean"] = self.learner_steps_mean
        if self.learner_steps_max is not None:
            payload["learner_steps_max"] = self.learner_steps_max
        if self.mean_candidate_actions_before is not None:
            payload["mean_candidate_actions_before"] = self.mean_candidate_actions_before
        if self.mean_candidate_actions_after is not None:
            payload["mean_candidate_actions_after"] = self.mean_candidate_actions_after
        if self.mean_reward_per_game_min is not None:
            payload["mean_reward_per_game_min"] = self.mean_reward_per_game_min
        if self.mean_reward_per_game_max is not None:
            payload["mean_reward_per_game_max"] = self.mean_reward_per_game_max
        if self.per_game is not None:
            payload["per_game"] = [dict(row) for row in self.per_game]
        if self.training_device is not None:
            payload["training_device"] = self.training_device
        return payload


@dataclass
class SelfPlayPhaseTimings:
    """Wall-clock breakdown for :func:`train_self_play` (mutable; optional out-parameter)."""

    rollout_seconds: float = 0.0
    ppo_update_seconds: float = 0.0
    total_seconds: float = 0.0
    mean_legal_actions_per_step: float = 0.0
    max_legal_actions_per_step: int = 0
    training_steps: int = 0
    ppo_updates: int = 0
    rollout_steps_per_update: tuple[int, ...] = ()
    truncated_games: int = 0
    candidate_actions_before: int = 0
    candidate_actions_after: int = 0
    candidate_actions_pruned: int = 0


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


def _effective_rollout_batch_games(config: PPOConfig) -> int:
    if config.rollout_batch_games < 1:
        raise ValueError("rollout_batch_games must be at least 1")
    # When games==0, range(0,0,step) must use step>=1; min(…,games) would be 0.
    capped = min(config.rollout_batch_games, max(config.games, 1))
    return max(1, capped)


def _validate_rollout_config(config: PPOConfig) -> None:
    if config.rollout_target_steps is not None and config.rollout_target_steps < 1:
        raise ValueError("rollout_target_steps must be at least 1")
    if config.min_rollout_games < 1:
        raise ValueError("min_rollout_games must be at least 1")
    if config.rollout_max_steps_per_game is not None and config.rollout_max_steps_per_game < 1:
        raise ValueError("rollout_max_steps_per_game must be at least 1")
    if config.max_policy_actions is not None and config.max_policy_actions < 1:
        raise ValueError("max_policy_actions must be at least 1")
    if config.rollout_workers < 1:
        raise ValueError("rollout_workers must be at least 1")
    if config.rollout_workers > 1 and config.rollout_target_steps is not None:
        raise ValueError(
            "rollout_workers>1 cannot be combined with rollout_target_steps "
            "(parallel batches do not preserve step-budget stopping semantics)."
        )


def _ppo_config_to_dict(config: PPOConfig) -> dict[str, Any]:
    payload = asdict(config)
    ck = payload.get("champion_checkpoint")
    if ck is not None:
        payload["champion_checkpoint"] = str(ck)
    return payload


def _cpu_policy_state(policy: Any) -> dict[str, Any]:
    return {key: tensor.detach().cpu().clone() for key, tensor in policy.state_dict().items()}


def _optimizer_state_cpu(torch_mod: Any, optimizer: Any) -> dict[str, Any]:
    """Move Adam state tensors to CPU before ``torch.save``."""

    def tensor_cpu(tensor: Any) -> Any:
        if torch_mod.is_tensor(tensor):
            return tensor.detach().clone().cpu()
        return tensor

    raw = optimizer.state_dict()
    out: dict[str, Any] = {}
    state_map = raw.get("state")
    if isinstance(state_map, dict):
        out_states: dict[int | str, dict[str, Any]] = {}
        for param_hash, pdata in state_map.items():
            if isinstance(pdata, dict):
                out_states[param_hash] = {key: tensor_cpu(val) for key, val in pdata.items()}
            else:
                out_states[param_hash] = pdata  # type: ignore[assignment]
        out["state"] = out_states
    if "param_groups" in raw:
        out["param_groups"] = list(raw["param_groups"])
    return out


def _move_optimizer_state_to_device(
    torch_mod: Any,
    state_dict: dict[str, Any],
    device: Any,
) -> dict[str, Any]:
    """Re-map optimizer snapshots onto ``device`` for ``load_state_dict``."""

    def move(tensor: Any) -> Any:
        if torch_mod.is_tensor(tensor):
            return tensor.to(device=device)
        return tensor

    out = dict(state_dict)
    state_map = state_dict.get("state")
    if isinstance(state_map, dict):
        out_states: dict[int | str, dict[str, Any]] = {}
        for param_hash, pdata in state_map.items():
            if isinstance(pdata, dict):
                out_states[param_hash] = {key: move(val) for key, val in pdata.items()}
            else:
                out_states[param_hash] = pdata  # type: ignore[assignment]
        out["state"] = out_states
    out["param_groups"] = state_dict["param_groups"]
    return out


def refresh_trajectory_policy_outputs(
    policy: Any,
    trajectory: SelfPlayTrajectory,
    torch_mod: Any,
) -> SelfPlayTrajectory:
    """Re-evaluate logits on the learner device after CPU-only parallel rollouts."""
    if not trajectory.steps:
        return trajectory
    device = next(policy.parameters()).device
    batches = [step.batch for step in trajectory.steps]
    indices = torch_mod.tensor(
        [step.action_index for step in trajectory.steps],
        dtype=torch_mod.long,
        device=device,
    )
    evaluated = evaluate_action_indices(policy, batches, indices)
    new_steps = [
        dataclasses.replace(
            step,
            log_prob=float(evaluated.log_probs[i].detach().item()),
            value=float(evaluated.values[i].detach().item()),
        )
        for i, step in enumerate(trajectory.steps)
    ]
    return SelfPlayTrajectory(
        steps=tuple(new_steps),
        rewards=trajectory.rewards,
        rankings=trajectory.rankings,
        ended_by=trajectory.ended_by,
        learner_seat=trajectory.learner_seat,
        fast_single_learner=trajectory.fast_single_learner,
        legal_action_counts_before_pruning=trajectory.legal_action_counts_before_pruning,
        legal_action_counts_after_pruning=trajectory.legal_action_counts_after_pruning,
    )


def _train_rollout_worker(args: tuple[dict[str, Any], int]) -> SelfPlayTrajectory:
    """Top-level trampoline for multiprocessing (must stay picklable)."""
    cfg, game_index = args
    from dbreaker.ml.trajectory import collect_training_trajectory

    model = build_policy_from_config(cfg["model_config"])
    model.load_state_dict(cfg["state_dict"])
    model.eval()
    seed = cfg["seed"]
    game_seed = None if seed is None else int(seed + game_index + cfg["game_seed_offset"])
    champ = cfg.get("champion_checkpoint")
    champ_path = Path(champ) if isinstance(champ, str) else None
    rollout_cap = cfg.get("rollout_max_steps_per_game")
    max_policy = cfg.get("max_policy_actions")
    pk_raw = cfg.get("policy_top_k", 3)
    policy_top_k = None if pk_raw is None else int(pk_raw)
    return collect_training_trajectory(
        model,
        player_count=int(cfg["player_count"]),
        seed=game_seed,
        max_turns=int(cfg["max_turns"]),
        max_self_play_steps=int(cfg["max_self_play_steps"]),
        opponent_mix_prob=float(cfg["opponent_mix_prob"]),
        opponent_strategies=tuple(cfg["opponent_strategies"]),
        champion_checkpoint=champ_path,
        single_learner=bool(cfg["fast_single_learner"]),
        rollout_max_steps_per_game=int(rollout_cap) if rollout_cap is not None else None,
        max_policy_actions=int(max_policy) if max_policy is not None else None,
        policy_top_k=policy_top_k,
        telemetry_jsonl=None,
        telemetry_game_index=None,
    )


def _rollout_target_reached(
    config: PPOConfig,
    trajectories: list[SelfPlayTrajectory],
    *,
    roll_batch: int,
) -> bool:
    if len(trajectories) >= roll_batch:
        return True
    if config.rollout_target_steps is None:
        return False
    if len(trajectories) < config.min_rollout_games:
        return False
    return sum(len(traj.steps) for traj in trajectories) >= config.rollout_target_steps


def _collect_rollout_batch(
    policy: Any,
    config: PPOConfig,
    *,
    start_game_index: int,
    roll_batch: int,
    seed: int | None,
    game_seed_offset: int,
    on_game_complete: TrajectoryProgress | None,
    telemetry_jsonl: Path | None,
    torch_module: Any,
) -> tuple[list[SelfPlayTrajectory], int]:
    """Collect rollouts respecting batch limits; parallel workers rerun on CPU snapshots."""
    batch_trajs: list[SelfPlayTrajectory] = []
    game_index = start_game_index
    while game_index < config.games:
        if len(batch_trajs) >= roll_batch:
            break
        slots_left = roll_batch - len(batch_trajs)

        if config.rollout_workers <= 1:
            trajectory = collect_training_trajectory(
                policy,
                player_count=config.player_count,
                seed=None if seed is None else seed + game_index + game_seed_offset,
                max_turns=config.max_turns,
                max_self_play_steps=config.max_self_play_steps,
                opponent_mix_prob=config.opponent_mix_prob,
                opponent_strategies=config.opponent_strategies,
                champion_checkpoint=config.champion_checkpoint,
                single_learner=config.fast_single_learner,
                rollout_max_steps_per_game=config.rollout_max_steps_per_game,
                max_policy_actions=config.max_policy_actions,
                policy_top_k=config.policy_top_k,
                telemetry_jsonl=telemetry_jsonl,
                telemetry_game_index=game_index,
            )
            batch_trajs.append(trajectory)
            if on_game_complete is not None:
                on_game_complete(game_index, trajectory)
            game_index += 1
            if _rollout_target_reached(config, batch_trajs, roll_batch=roll_batch):
                break
            continue

        wave = min(slots_left, config.games - game_index)
        static_cfg = dict(_ppo_config_to_dict(config))
        static_cfg["seed"] = seed
        static_cfg["game_seed_offset"] = game_seed_offset
        static_cfg["model_config"] = policy.model_config()
        static_cfg["state_dict"] = _cpu_policy_state(policy)

        payloads = [(static_cfg, idx) for idx in range(game_index, game_index + wave)]
        ctx = mp.get_context("spawn")
        max_workers = min(config.rollout_workers, wave)
        with ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as executor:
            traj_chunk = list(executor.map(_train_rollout_worker, payloads))
        traj_chunk = [
            refresh_trajectory_policy_outputs(policy, traj, torch_module)
            for traj in traj_chunk
        ]
        offset = game_index
        for traj in traj_chunk:
            batch_trajs.append(traj)
            if on_game_complete is not None:
                on_game_complete(offset, traj)
            offset += 1
        game_index += wave
        if _rollout_target_reached(config, batch_trajs, roll_batch=roll_batch):
            break
    return batch_trajs, game_index


def _ppo_update_from_trajectories(
    policy: Any,
    optimizer: Any,
    config: PPOConfig,
    trajectories: list[SelfPlayTrajectory],
    torch: Any,
) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    """Returns last-epoch scalar metrics after PPO updates, or None if no steps."""
    steps = [step for trajectory in trajectories for step in trajectory.steps]
    if not steps:
        return None, None, None, None, None
    device = next(policy.parameters()).device
    sparse_parts: list[float] = []
    for trajectory in trajectories:
        reward_by_player = {
            step.player_id: reward
            for step, reward in zip(trajectory.steps, trajectory.rewards, strict=True)
        }
        sparse_parts.extend(
            sparse_terminal_rewards_for_steps(trajectory.steps, reward_by_player)
        )
    old_log_probs = torch.tensor(
        [step.log_prob for step in steps],
        dtype=torch.float32,
        device=device,
    )
    old_values = torch.tensor(
        [step.value for step in steps],
        dtype=torch.float32,
        device=device,
    )
    sparse_rewards = torch.tensor(sparse_parts, dtype=torch.float32, device=device)
    returns = _discounted_returns(sparse_rewards, config.gamma, torch)
    advantages = returns - old_values.detach()
    adv_std = advantages.std(unbiased=False)
    if adv_std > 1e-8:
        advantages = (advantages - advantages.mean()) / (adv_std + 1e-8)
    action_indices = torch.tensor(
        [step.action_index for step in steps],
        dtype=torch.long,
        device=device,
    )
    batches = [step.batch for step in steps]

    mean_entropy: float | None = None
    policy_loss_f: float | None = None
    value_loss_f: float | None = None
    total_loss_f: float | None = None
    clip_fraction_f: float | None = None
    n = len(steps)
    micro = evaluation_forward_chunk_size(device)
    for _ in range(config.update_epochs):
        sum_entropy = 0.0
        sum_clip_frac = 0.0
        sum_pl = 0.0
        sum_vl = 0.0
        sum_tl = 0.0
        optimizer.zero_grad()
        for start in range(0, n, micro):
            end = min(start + micro, n)
            w = (end - start) / n
            batches_slice = batches[start:end]
            evaluated = evaluate_action_indices(
                policy,
                batches_slice,
                action_indices[start:end],
                chunk_size=micro,
            )
            ratios = torch.exp(evaluated.log_probs - old_log_probs[start:end])
            clipped = torch.clamp(
                ratios,
                1.0 - config.clip_epsilon,
                1.0 + config.clip_epsilon,
            )
            advantages_slice = advantages[start:end]
            policy_loss = -torch.min(
                ratios * advantages_slice,
                clipped * advantages_slice,
            ).mean()
            value_loss = torch.nn.functional.mse_loss(
                evaluated.values,
                returns[start:end],
                reduction="mean",
            )
            entropy_bonus = evaluated.entropies.mean()
            clip_fraction_mb = torch.mean(
                (torch.abs(ratios - 1.0) > config.clip_epsilon).float(),
            )
            loss = (
                policy_loss * w
                + config.value_coef * value_loss * w
                - config.entropy_coef * entropy_bonus * w
            )
            loss.backward()
            k = float(end - start)
            sum_entropy += float(entropy_bonus.detach().item()) * k
            sum_clip_frac += float(clip_fraction_mb.detach().item()) * k
            sum_pl += float(policy_loss.detach().item()) * k
            sum_vl += float(value_loss.detach().item()) * k
            sum_tl += float(loss.detach().item())
        optimizer.step()
        inv_n = 1.0 / float(n)
        mean_entropy = sum_entropy * inv_n
        clip_fraction_f = sum_clip_frac * inv_n
        policy_loss_f = sum_pl * inv_n
        value_loss_f = sum_vl * inv_n
        total_loss_f = sum_tl
    return (
        mean_entropy,
        policy_loss_f,
        value_loss_f,
        total_loss_f,
        clip_fraction_f,
    )


def train_self_play(
    config: PPOConfig,
    *,
    checkpoint_out: Path | None = None,
    seed: int | None = None,
    model: PolicyValueNetwork | StructuredPolicyValueNetwork | None = None,
    from_checkpoint: Path | None = None,
    structured_policy: bool = False,
    game_seed_offset: int = 0,
    phase_timings: SelfPlayPhaseTimings | None = None,
    torch_seed: int | None = None,
    on_game_complete: TrajectoryProgress | None = None,
    metrics_out: Path | None = None,
    telemetry_jsonl: Path | None = None,
    device: str = "auto",
) -> TrainingStats:
    exclusive = sum(
        1 for x in (model is not None, from_checkpoint is not None, structured_policy) if x
    )
    if exclusive > 1:
        raise ValueError(
            "pass at most one of model=, from_checkpoint=, and structured_policy=True",
        )
    _validate_rollout_config(config)
    if telemetry_jsonl is not None and config.rollout_workers > 1:
        raise ValueError(
            "telemetry_jsonl requires rollout_workers=1; parallel rollout workers omit JSONL telemetry."
        )
    torch = require_torch()
    dev = resolve_training_device(torch, device)
    if torch_seed is not None:
        torch.manual_seed(torch_seed)
    continued_from: str | None = None
    loaded_ckpt: LoadedCheckpoint | None = None
    if from_checkpoint is not None:
        loaded_ckpt = load_checkpoint(from_checkpoint, map_location=dev)
        policy = loaded_ckpt.model
        continued_from = str(from_checkpoint)
    elif model is not None:
        policy = model
    elif structured_policy:
        policy = StructuredPolicyValueNetwork()
    else:
        policy = PolicyValueNetwork()
    policy = policy.to(dev)
    policy.train()
    optimizer = torch.optim.Adam(policy.parameters(), lr=config.learning_rate)
    if loaded_ckpt is not None and loaded_ckpt.optimizer_state is not None:
        restored = _move_optimizer_state_to_device(torch, loaded_ckpt.optimizer_state, dev)
        optimizer.load_state_dict(restored)
    roll_batch = _effective_rollout_batch_games(config)
    total_t0 = time.perf_counter()
    rollout_seconds = 0.0
    ppo_update_seconds = 0.0

    per_game_rows: list[dict[str, Any]] = []
    ended_counts: Counter[str] = Counter()
    lengths: list[int] = []
    rewards_dense_all: list[float] = []
    rollout_steps_per_update: list[int] = []

    legal_sum = 0
    legal_max = 0
    n_steps = 0
    candidate_before = 0
    candidate_after = 0
    candidate_step_count = 0

    sum_weight = 0.0
    w_entropy = w_pl = w_vl = w_tl = w_cf = 0.0

    game_index = 0
    while game_index < config.games:
        start = game_index
        rollout_t0 = time.perf_counter()
        batch_trajs, game_index = _collect_rollout_batch(
            policy,
            config,
            start_game_index=start,
            roll_batch=roll_batch,
            seed=seed,
            game_seed_offset=game_seed_offset,
            on_game_complete=on_game_complete,
            telemetry_jsonl=telemetry_jsonl,
            torch_module=torch,
        )
        rollout_seconds += time.perf_counter() - rollout_t0

        for gi, traj in enumerate(batch_trajs):
            gidx = start + gi
            per_game_rows.append(
                {
                    "game_index": gidx,
                    "learner_steps": len(traj.steps),
                    "ended_by": traj.ended_by,
                    "mean_reward": _mean_reward_for_trajectory(traj),
                    "learner_seat": traj.learner_seat,
                    "fast_single_learner": traj.fast_single_learner,
                    "candidate_actions_before": sum(
                        traj.legal_action_counts_before_pruning
                    ),
                    "candidate_actions_after": sum(
                        traj.legal_action_counts_after_pruning
                    ),
                }
            )
            ended_counts[traj.ended_by] += 1
            lengths.append(len(traj.steps))
            rewards_dense_all.extend(traj.rewards)
            candidate_before += sum(traj.legal_action_counts_before_pruning)
            candidate_after += sum(traj.legal_action_counts_after_pruning)
            candidate_step_count += len(traj.legal_action_counts_before_pruning)
            for step, legal_n in zip(
                traj.steps,
                traj.legal_action_counts_after_pruning,
                strict=True,
            ):
                legal_sum += legal_n
                legal_max = max(legal_max, legal_n)

        n_chunk = sum(len(traj.steps) for traj in batch_trajs)
        n_steps += n_chunk
        if n_chunk > 0:
            rollout_steps_per_update.append(n_chunk)

        ppo_t0 = time.perf_counter()
        e, pl, vl, tl, cf = _ppo_update_from_trajectories(policy, optimizer, config, batch_trajs, torch)
        ppo_update_seconds += time.perf_counter() - ppo_t0

        if e is not None and n_chunk > 0:
            w = float(n_chunk)
            sum_weight += w
            w_entropy += e * w
            if pl is not None:
                w_pl += pl * w
            if vl is not None:
                w_vl += vl * w
            if tl is not None:
                w_tl += tl * w
            if cf is not None:
                w_cf += cf * w

        del batch_trajs

    mean_reward = (
        sum(rewards_dense_all) / len(rewards_dense_all) if rewards_dense_all else 0.0
    )
    total_seconds = time.perf_counter() - total_t0

    mean_entropy: float | None = None
    policy_loss_f: float | None = None
    value_loss_f: float | None = None
    total_loss_f: float | None = None
    clip_fraction_f: float | None = None
    if sum_weight > 0.0:
        mean_entropy = w_entropy / sum_weight
        policy_loss_f = w_pl / sum_weight
        value_loss_f = w_vl / sum_weight
        total_loss_f = w_tl / sum_weight
        clip_fraction_f = w_cf / sum_weight

    mean_legal = float(legal_sum) / float(n_steps) if n_steps else 0.0
    learner_mean = float(sum(lengths) / len(lengths)) if lengths else 0.0
    learner_max = max(lengths) if lengths else 0
    truncated_games = sum(
        count
        for reason, count in ended_counts.items()
        if reason in {"max_turns", "truncated_steps"}
    )
    candidate_pruned = candidate_before - candidate_after
    mean_candidate_before = (
        float(candidate_before) / float(candidate_step_count)
        if candidate_step_count
        else 0.0
    )
    mean_candidate_after = (
        float(candidate_after) / float(candidate_step_count)
        if candidate_step_count
        else 0.0
    )
    mr_vals = [float(row["mean_reward"]) for row in per_game_rows]
    mr_min = min(mr_vals) if mr_vals else 0.0
    mr_max = max(mr_vals) if mr_vals else 0.0

    stats = TrainingStats(
        games=config.games,
        steps=n_steps,
        mean_reward=mean_reward,
        checkpoint_path=str(checkpoint_out) if checkpoint_out is not None else None,
        rollout_batch_games=config.rollout_batch_games,
        rollout_target_steps=config.rollout_target_steps,
        min_rollout_games=config.min_rollout_games,
        fast_single_learner=config.fast_single_learner,
        rollout_max_steps_per_game=config.rollout_max_steps_per_game,
        max_policy_actions=config.max_policy_actions,
        ppo_updates=len(rollout_steps_per_update),
        rollout_steps_per_update=tuple(rollout_steps_per_update),
        mean_entropy=mean_entropy,
        policy_loss=policy_loss_f,
        value_loss=value_loss_f,
        total_loss=total_loss_f,
        clip_fraction=clip_fraction_f,
        rollout_seconds=rollout_seconds,
        ppo_update_seconds=ppo_update_seconds,
        total_seconds=total_seconds,
        mean_legal_actions_per_step=mean_legal,
        max_legal_actions_per_step=legal_max,
        ended_by=dict(ended_counts),
        learner_steps_mean=learner_mean,
        learner_steps_max=learner_max,
        truncated_games=truncated_games,
        candidate_actions_before=candidate_before,
        candidate_actions_after=candidate_after,
        candidate_actions_pruned=candidate_pruned,
        mean_candidate_actions_before=mean_candidate_before,
        mean_candidate_actions_after=mean_candidate_after,
        mean_reward_per_game_min=mr_min,
        mean_reward_per_game_max=mr_max,
        per_game=tuple(per_game_rows),
        continued_from=continued_from,
        game_seed_offset=game_seed_offset,
        training_device=str(dev),
    )
    if checkpoint_out is not None:
        save_checkpoint(
            checkpoint_out,
            model=policy,
            training_stats=stats.as_dict(),
            optimizer_state=_optimizer_state_cpu(torch, optimizer),
            ppo_config=_ppo_config_to_dict(config),
        )
    if phase_timings is not None:
        phase_timings.rollout_seconds = rollout_seconds
        phase_timings.ppo_update_seconds = ppo_update_seconds
        phase_timings.total_seconds = total_seconds
        phase_timings.training_steps = n_steps
        phase_timings.mean_legal_actions_per_step = mean_legal
        phase_timings.max_legal_actions_per_step = legal_max
        phase_timings.ppo_updates = len(rollout_steps_per_update)
        phase_timings.rollout_steps_per_update = tuple(rollout_steps_per_update)
        phase_timings.truncated_games = truncated_games
        phase_timings.candidate_actions_before = candidate_before
        phase_timings.candidate_actions_after = candidate_after
        phase_timings.candidate_actions_pruned = candidate_pruned
    if metrics_out is not None:
        metrics_out.parent.mkdir(parents=True, exist_ok=True)
        metrics_out.write_text(
            json.dumps(stats.as_dict(), indent=2),
            encoding="utf-8",
        )
    return stats

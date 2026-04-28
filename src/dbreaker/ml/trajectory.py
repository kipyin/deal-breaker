from __future__ import annotations

import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dbreaker.engine.actions import (
    Action,
    BankCard,
    DiscardCard,
    DrawCards,
    EndTurn,
    PayWithAssets,
    PlayActionCard,
    PlayProperty,
    PlayRent,
    RearrangeProperty,
    RespondJustSayNo,
)
from dbreaker.engine.game import Game
from dbreaker.ml.features import EncodedActionBatch, encode_legal_actions
from dbreaker.ml.model import choose_action_index, require_torch
from dbreaker.strategies.base import BaseStrategy
from dbreaker.strategies.neural import NeuralStrategy
from dbreaker.strategies.registry import create_strategy

_TRAINING_NEURAL_PATH = Path("__training__")


@dataclass(frozen=True, slots=True)
class TrajectoryStep:
    player_id: str
    batch: EncodedActionBatch
    action_index: int
    log_prob: float
    value: float
    action_type_name: str = ""
    phase_name: str | None = None
    completed_sets_delta: int | None = None
    asset_value_delta: int | None = None
    policy_topk_indices: tuple[int, ...] = ()
    policy_topk_probs: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class SelfPlayTrajectory:
    steps: tuple[TrajectoryStep, ...]
    rewards: tuple[float, ...]
    rankings: tuple[str, ...]
    ended_by: str
    learner_seat: int | None = None
    fast_single_learner: bool = False
    legal_action_counts_before_pruning: tuple[int, ...] = ()
    legal_action_counts_after_pruning: tuple[int, ...] = ()


def prune_policy_actions(
    legal_actions: Sequence[Action],
    *,
    max_policy_actions: int | None,
) -> list[Action]:
    """Keep a cheap, stable candidate set before neural scoring.

    Forced response/payment actions and explicit turn-ending actions are ranked ahead of
    exploratory actions so truncation does not make the policy pick illegal or impossible
    moves. This is an opt-in approximation for throughput experiments.
    """
    if max_policy_actions is None or len(legal_actions) <= max_policy_actions:
        return list(legal_actions)
    if max_policy_actions < 1:
        raise ValueError("max_policy_actions must be at least 1")

    ranked = sorted(
        enumerate(legal_actions),
        key=lambda item: (-_policy_action_priority(item[1]), item[0]),
    )
    keep_indices = sorted(index for index, _action in ranked[:max_policy_actions])
    return [legal_actions[index] for index in keep_indices]


def _policy_action_priority(action: Action) -> int:
    if isinstance(action, (PayWithAssets, RespondJustSayNo)):
        return 100
    if isinstance(action, EndTurn):
        return 90
    if isinstance(action, PlayProperty):
        return 80
    if isinstance(action, (PlayRent, PlayActionCard)):
        return 70
    if isinstance(action, DrawCards):
        return 60
    if isinstance(action, BankCard):
        return 50
    if isinstance(action, RearrangeProperty):
        return 40
    if isinstance(action, DiscardCard):
        return 30
    return 0


def sparse_terminal_rewards_for_steps(
    steps: Sequence[TrajectoryStep],
    reward_by_player: dict[str, float],
) -> tuple[float, ...]:
    """One non-zero reward at each player's final timestep (rank-based outcome)."""
    if not steps:
        return ()
    last_index: dict[str, int] = {}
    for i, step in enumerate(steps):
        last_index[step.player_id] = i
    sparse = [0.0] * len(steps)
    for player_id, idx in last_index.items():
        sparse[idx] = reward_by_player[player_id]
    return tuple(sparse)


def collect_training_trajectory(
    model: Any,
    *,
    player_count: int,
    seed: int | None = None,
    max_turns: int = 200,
    max_self_play_steps: int = 30_000,
    opponent_mix_prob: float = 0.0,
    opponent_strategies: tuple[str, ...] = (
        "basic",
        "aggressive",
        "defensive",
        "set_completion",
    ),
    champion_checkpoint: Path | None = None,
    single_learner: bool = False,
    rollout_max_steps_per_game: int | None = None,
    max_policy_actions: int | None = None,
    policy_top_k: int | None = 3,
    telemetry_jsonl: Path | None = None,
    telemetry_game_index: int | None = None,
) -> SelfPlayTrajectory:
    """Roll out a game; optionally mix in heuristic / champion opponents for one learner seat."""
    torch = require_torch()
    if rollout_max_steps_per_game is not None and rollout_max_steps_per_game < 1:
        raise ValueError("rollout_max_steps_per_game must be at least 1")
    if max_policy_actions is not None and max_policy_actions < 1:
        raise ValueError("max_policy_actions must be at least 1")
    if policy_top_k is not None and policy_top_k < 0:
        raise ValueError("policy_top_k must be non-negative or None")
    rng = random.Random(seed if seed is not None else 0xC0FFEE)
    use_mix = single_learner or (opponent_mix_prob > 0.0 and rng.random() < opponent_mix_prob)
    train_net = NeuralStrategy(_TRAINING_NEURAL_PATH, model=model)

    strategies: list[BaseStrategy] | None = None
    learner_seat = 0
    if use_mix:
        learner_seat = rng.randint(0, player_count - 1)
        pool = list(opponent_strategies)
        if champion_checkpoint is not None:
            pool.append(f"neural:{champion_checkpoint}")
        if not pool:
            raise ValueError("opponent_strategies must not be empty in single-learner mode")
        strategies = []
        for seat in range(player_count):
            if seat == learner_seat:
                strategies.append(train_net)
            else:
                strategies.append(create_strategy(rng.choice(pool)))

    game = Game.new(player_count=player_count, seed=seed, record_transitions=False)
    learner_id: str | None
    if use_mix:
        learner_id = game.state.player_order[learner_seat]
    else:
        learner_id = None
    seat_by_player = {pid: idx for idx, pid in enumerate(game.state.player_order)}

    steps: list[TrajectoryStep] = []
    legal_before_counts: list[int] = []
    legal_after_counts: list[int] = []
    steps_taken = 0
    ended_by = "max_turns"
    while not game.is_terminal() and game.state.turn <= max_turns:
        if rollout_max_steps_per_game is not None and steps_taken >= rollout_max_steps_per_game:
            ended_by = "truncated_steps"
            break
        if steps_taken >= max_self_play_steps:
            ended_by = "aborted"
            break
        player_id = game.active_player_id
        legal_actions = game.legal_actions(player_id)
        if not legal_actions:
            ended_by = "aborted"
            break
        seat = seat_by_player[player_id]
        record = learner_id is None or player_id == learner_id
        if record:
            policy_actions = prune_policy_actions(
                legal_actions,
                max_policy_actions=max_policy_actions,
            )
            legal_before_counts.append(len(legal_actions))
            legal_after_counts.append(len(policy_actions))
            observation = game.observation_for(player_id)
            learner_state = game.state.players[player_id]
            completed_before = learner_state.completed_set_count()
            assets_before = learner_state.asset_value
            phase_name = observation.phase.value
            batch = encode_legal_actions(observation, policy_actions)
            tk_arg = policy_top_k if (policy_top_k is not None and policy_top_k > 0) else None
            with torch.inference_mode():
                selection = choose_action_index(
                    model,
                    batch,
                    greedy=False,
                    include_entropy=False,
                    top_k=tk_arg,
                )
            chosen = policy_actions[selection.index]
            action_type_name = type(chosen).__name__
            result = game.step(player_id, chosen)
            learner_after = game.state.players[player_id]
            delta_sets = learner_after.completed_set_count() - completed_before
            delta_assets = learner_after.asset_value - assets_before
            step_row = TrajectoryStep(
                player_id=player_id,
                batch=batch,
                action_index=selection.index,
                log_prob=selection.log_prob,
                value=selection.value,
                action_type_name=action_type_name,
                phase_name=phase_name,
                completed_sets_delta=delta_sets,
                asset_value_delta=delta_assets,
                policy_topk_indices=selection.policy_topk_indices,
                policy_topk_probs=selection.policy_topk_probs,
            )
            steps.append(step_row)
            if telemetry_jsonl is not None:
                telemetry_jsonl.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "game_index": telemetry_game_index,
                    "player_id": player_id,
                    "action_type": action_type_name,
                    "phase": phase_name,
                    "completed_sets_delta": delta_sets,
                    "asset_value_delta": delta_assets,
                    "policy_topk_indices": list(selection.policy_topk_indices),
                    "policy_topk_probs": list(selection.policy_topk_probs),
                }
                with telemetry_jsonl.open("a", encoding="utf-8") as tf:
                    tf.write(json.dumps(payload, sort_keys=True) + "\n")
        else:
            assert strategies is not None
            decision = strategies[seat].choose_action(
                game.observation_for(player_id), legal_actions
            )
            result = game.step(player_id, decision.action)
        steps_taken += 1
        if not result.accepted:
            ended_by = "aborted"
            break
    if game.is_terminal():
        ended_by = "winner"
    rankings = tuple(_player_rankings(game))
    reward_by_player = _reward_by_player(rankings)
    rewards = tuple(reward_by_player[step.player_id] for step in steps)
    return SelfPlayTrajectory(
        steps=tuple(steps),
        rewards=rewards,
        rankings=rankings,
        ended_by=ended_by,
        learner_seat=learner_seat if use_mix else None,
        fast_single_learner=single_learner,
        legal_action_counts_before_pruning=tuple(legal_before_counts),
        legal_action_counts_after_pruning=tuple(legal_after_counts),
    )


def collect_self_play_trajectory(
    model: Any,
    *,
    player_count: int,
    seed: int | None = None,
    max_turns: int = 200,
    max_self_play_steps: int = 30_000,
) -> SelfPlayTrajectory:
    return collect_training_trajectory(
        model,
        player_count=player_count,
        seed=seed,
        max_turns=max_turns,
        max_self_play_steps=max_self_play_steps,
        opponent_mix_prob=0.0,
    )


def _player_rankings(game: Game) -> list[str]:
    return sorted(
        game.state.player_order,
        key=lambda player_id: (
            game.state.winner_id is not None and player_id != game.state.winner_id,
            -game.state.players[player_id].completed_set_count(),
            -game.state.players[player_id].asset_value,
        ),
    )


def _reward_by_player(rankings: tuple[str, ...]) -> dict[str, float]:
    if len(rankings) == 1:
        return {rankings[0]: 0.0}
    last_rank = len(rankings) - 1
    return {
        player_id: 1.0 - (2.0 * rank / last_rank)
        for rank, player_id in enumerate(rankings)
    }

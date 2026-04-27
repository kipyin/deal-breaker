from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from dbreaker.engine.game import Game
from dbreaker.ml.features import EncodedActionBatch, encode_legal_actions
from dbreaker.ml.model import PolicyValueNetwork, choose_action_index
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


@dataclass(frozen=True, slots=True)
class SelfPlayTrajectory:
    steps: tuple[TrajectoryStep, ...]
    rewards: tuple[float, ...]
    rankings: tuple[str, ...]
    ended_by: str


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
    model: PolicyValueNetwork,
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
) -> SelfPlayTrajectory:
    """Roll out a game; optionally mix in heuristic / champion opponents for one learner seat."""
    rng = random.Random(seed if seed is not None else 0xC0FFEE)
    use_mix = opponent_mix_prob > 0.0 and rng.random() < opponent_mix_prob
    train_net = NeuralStrategy(_TRAINING_NEURAL_PATH, model=model)

    strategies: list[BaseStrategy] | None = None
    learner_seat = 0
    if use_mix:
        learner_seat = rng.randint(0, player_count - 1)
        pool = list(opponent_strategies)
        if champion_checkpoint is not None:
            pool.append(f"neural:{champion_checkpoint}")
        strategies = []
        for seat in range(player_count):
            if seat == learner_seat:
                strategies.append(train_net)
            else:
                strategies.append(create_strategy(rng.choice(pool)))

    game = Game.new(player_count=player_count, seed=seed)
    learner_id: str | None
    if use_mix:
        learner_id = game.state.player_order[learner_seat]
    else:
        learner_id = None

    steps: list[TrajectoryStep] = []
    steps_taken = 0
    ended_by = "max_turns"
    while not game.is_terminal() and game.state.turn <= max_turns:
        if steps_taken >= max_self_play_steps:
            ended_by = "aborted"
            break
        player_id = game.active_player_id
        legal_actions = game.legal_actions(player_id)
        if not legal_actions:
            ended_by = "aborted"
            break
        seat = game.state.player_order.index(player_id)
        record = learner_id is None or player_id == learner_id
        if record:
            batch = encode_legal_actions(game.observation_for(player_id), legal_actions)
            selection = choose_action_index(model, batch, greedy=False)
            steps.append(
                TrajectoryStep(
                    player_id=player_id,
                    batch=batch,
                    action_index=selection.index,
                    log_prob=selection.log_prob,
                    value=selection.value,
                )
            )
            result = game.step(player_id, legal_actions[selection.index])
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
    )


def collect_self_play_trajectory(
    model: PolicyValueNetwork,
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

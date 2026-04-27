from __future__ import annotations

from dataclasses import dataclass

from dbreaker.engine.game import Game
from dbreaker.ml.features import EncodedActionBatch, encode_legal_actions
from dbreaker.ml.model import PolicyValueNetwork, choose_action_index


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


def collect_self_play_trajectory(
    model: PolicyValueNetwork,
    *,
    player_count: int,
    seed: int | None = None,
    max_turns: int = 200,
    max_self_play_steps: int = 30_000,
) -> SelfPlayTrajectory:
    game = Game.new(player_count=player_count, seed=seed)
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

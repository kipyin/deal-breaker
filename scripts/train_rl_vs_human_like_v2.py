#!/usr/bin/env python3
"""Train a neural PPO policy for 3p games until it beats ``human_like_v2`` consistently.

Loads optional ML deps (torch) only when run; not imported at collection time for core tests.

Run (from repo root, with ``uv run --extra ml`` or an env with torch):

  uv run --extra ml python scripts/train_rl_vs_human_like_v2.py

Artifacts default to ``checkpoints/human-like-v2-champion/`` (gitignored; see ``.gitignore``).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from dbreaker.experiments.rl_search import (  # noqa: E402
    EvaluationConfig,
    evaluate_candidate,
)
from dbreaker.ml.trainer import PPOConfig, train_self_play  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("checkpoints/human-like-v2-champion"),
        help="Directory for checkpoint and run log JSON",
    )
    p.add_argument("--players", type=int, default=3, choices=[2, 3, 4, 5])
    p.add_argument("--seed", type=int, default=20260506)
    p.add_argument("--device", default="auto", help="cpu|cuda|mps|auto")
    p.add_argument(
        "--games-per-round",
        type=int,
        default=200,
        help="PPO self-play games per training round (same checkpoint overwritten).",
    )
    p.add_argument(
        "--rollout-batch-games",
        type=int,
        default=50,
        help="Games per PPO minibatch inside a round.",
    )
    p.add_argument(
        "--max-rounds",
        type=int,
        default=25,
        help="Safety cap on train/eval outer iterations.",
    )
    p.add_argument(
        "--eval-games",
        type=int,
        default=120,
        help="Tournament games per eval (rotating seats).",
    )
    p.add_argument(
        "--min-win-rate-margin",
        type=float,
        default=0.03,
        help="Require neural win_rate >= teacher win_rate + this (3p rotated tournament).",
    )
    p.add_argument(
        "--min-rating-gap",
        type=float,
        default=12.0,
        help="Require candidate Elo - human_like_v2 Elo >= this.",
    )
    p.add_argument(
        "--consecutive-passes",
        type=int,
        default=2,
        help="Stop after this many eval rounds pass the gates in a row.",
    )
    p.add_argument(
        "--opponent-mix",
        type=float,
        default=0.4,
        help="Mix prob. for heuristic opponents vs self-play; unused with --fast-single-learner.",
    )
    p.add_argument(
        "--max-self-play-steps",
        type=int,
        default=30_000,
    )
    p.add_argument("--max-turns", type=int, default=200)
    p.add_argument("--update-epochs", type=int, default=2)
    p.add_argument("--gamma", type=float, default=0.99)
    p.add_argument(
        "--reward-completed-set",
        type=float,
        default=0.35,
        help="PPO dense shaping weight on completed-set deltas (see train --reward-completed-set).",
    )
    p.add_argument(
        "--reward-asset-value",
        type=float,
        default=0.25,
    )
    p.add_argument(
        "--reward-opponent-completed-set",
        type=float,
        default=0.12,
    )
    p.add_argument(
        "--reward-terminal-rank",
        type=float,
        default=1.0,
        help="Weight on sparse terminal rank reward (see train --reward-terminal-rank).",
    )
    p.add_argument(
        "--policy-top-k",
        type=int,
        default=0,
        help="Top-k extra logits (0 disables for faster rollouts).",
    )
    p.add_argument(
        "--fast-single-learner",
        action="store_true",
        help="One neural seat per game; others are heuristics (often faster).",
    )
    return p.parse_args()


def _eval_key(
    *,
    neural_win_rate: float,
    teacher_win_rate: float,
    rating_gap: float,
    min_delta: float,
    min_gap: float,
) -> tuple[bool, str]:
    ok_win = neural_win_rate >= teacher_win_rate + min_delta
    ok_elo = rating_gap >= min_gap
    if ok_win and ok_elo:
        return True, "pass"
    parts = []
    if not ok_win:
        parts.append(
            f"win_rate neural={neural_win_rate:.3f} vs teacher={teacher_win_rate:.3f} "
            f"(need +{min_delta} margin)",
        )
    if not ok_elo:
        parts.append(f"elo_gap {rating_gap:.1f} < {min_gap}")
    return False, "; ".join(parts)


def main() -> int:
    args = _parse_args()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt = out_dir / "policy.pt"
    log_path = out_dir / "training_run.json"

    baselines = ("human_like_v2",)
    opponents = ("human_like_v2", "basic", "aggressive", "defensive", "set_completion")

    rounds_log: list[dict] = []
    cumulative_games = 0
    passes_in_a_row = 0
    game_seed_offset = 0

    for round_ix in range(1, args.max_rounds + 1):
        train_seed = args.seed + round_ix * 9973
        ppo = PPOConfig(
            games=args.games_per_round,
            rollout_batch_games=min(args.rollout_batch_games, args.games_per_round),
            player_count=args.players,
            max_turns=args.max_turns,
            max_self_play_steps=args.max_self_play_steps,
            update_epochs=args.update_epochs,
            gamma=args.gamma,
            opponent_mix_prob=args.opponent_mix,
            opponent_strategies=opponents,
            champion_checkpoint=None,
            policy_pool_manifest=None,
            opponent_neural_checkpoints=(),
            reward_terminal_rank_weight=args.reward_terminal_rank,
            reward_completed_set_delta_weight=args.reward_completed_set,
            reward_asset_value_delta_weight=args.reward_asset_value,
            reward_opponent_completed_set_delta_weight=args.reward_opponent_completed_set,
            fast_single_learner=args.fast_single_learner,
            rollout_workers=args.rollout_workers,
            policy_top_k=None if args.policy_top_k == 0 else args.policy_top_k,
        )
        from_checkpoint = ckpt if ckpt.exists() else None
        stats = train_self_play(
            ppo,
            checkpoint_out=ckpt,
            seed=train_seed,
            from_checkpoint=from_checkpoint,
            game_seed_offset=game_seed_offset,
            device=args.device,
        )
        cumulative_games += stats.games
        game_seed_offset += stats.games

        candidate_spec = f"neural:{ckpt}"
        ev = evaluate_candidate(
            EvaluationConfig(
                player_count=args.players,
                candidate=candidate_spec,
                baselines=baselines,
                champions_path=None,
                games=args.eval_games,
                seed=args.seed + round_ix * 4099,
                max_turns=args.max_turns,
                max_self_play_steps=args.max_self_play_steps,
            ),
        )
        teacher = "human_like_v2"
        tsum = ev.report.summaries[teacher]
        neural_sum = ev.report.summaries[candidate_spec]
        neural_wr = neural_sum.win_rate
        teacher_wr = tsum.win_rate
        elo_teacher = ev.report.ratings[teacher]
        elo_neural = ev.report.ratings[candidate_spec]
        rating_gap = elo_neural - elo_teacher

        passed, reason = _eval_key(
            neural_win_rate=neural_wr,
            teacher_win_rate=teacher_wr,
            rating_gap=rating_gap,
            min_delta=args.min_win_rate_margin,
            min_gap=args.min_rating_gap,
        )
        if passed:
            passes_in_a_row += 1
        else:
            passes_in_a_row = 0

        round_record = {
            "round": round_ix,
            "train_seed": train_seed,
            "cumulative_train_games": cumulative_games,
            "training": stats.as_dict(),
            "eval_neural_win_rate": neural_wr,
            "eval_teacher_win_rate": teacher_wr,
            "eval_elo_neural": elo_neural,
            "eval_elo_teacher": elo_teacher,
            "eval_elo_gap": rating_gap,
            "eval_passed": passed,
            "eval_reason": reason,
            "passes_in_a_row": passes_in_a_row,
            "report_markdown": ev.report.to_markdown(),
        }
        rounds_log.append(round_record)
        cfg_dump = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
        log_path.write_text(
            json.dumps(
                {
                    "config": cfg_dump,
                    "checkpoint": str(ckpt),
                    "rounds": rounds_log,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        print(f"\n=== Round {round_ix} ===", flush=True)
        print(
            f"train games this round={stats.games} cumulative={cumulative_games} "
            f"checkpoint={ckpt}",
            flush=True,
        )
        print(
            f"eval: neural_wr={neural_wr:.3f} teacher_wr={teacher_wr:.3f} "
            f"elo_gap={rating_gap:.1f} ({'PASS' if passed else 'FAIL'}: {reason})",
            flush=True,
        )
        if passes_in_a_row >= args.consecutive_passes:
            print(
                f"\nStopped: {args.consecutive_passes} consecutive eval passes "
                f"(consistent edge over {teacher}).",
                flush=True,
            )
            return 0

    print(f"\nStopped: reached --max-rounds={args.max_rounds} without stable pass.", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

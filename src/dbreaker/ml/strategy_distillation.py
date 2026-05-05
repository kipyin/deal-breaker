"""Distill a neural policy toward the `HumanLikeStrategy` (or other teachers).

Design notes (stub — not implemented)
-------------------------------------
- **Objective**: supervised loss between teacher logits / action labels and student,
  optionally mixed with on-policy PPO to avoid covariate shift.
- **Data**: replay self-play trajectories with `(observation, legal mask, teacher_action)`
  where the teacher is a registered `BaseStrategy` (e.g. ``human_like``).
- **Alignment with ML features**: training rows must use `FEATURE_SCHEMA_VERSION` from
  `dbreaker.ml.features`; bumping the schema invalidates old checkpoints — distillation
  should tag batches with the same version as the student network.
- **Fair information**: the human_like teacher only uses observation-visible cards plus
  deck constants; distilled labels stay cheating-free for fair-info students.
- **Reward shaping**: extra dense shaping tied to heuristic objectives was **not** added
  to `Trajectory` / PPO — it would couple rewards to a brittle heuristic and risk
  conflicting with the existing sparse terminal signal; revisit only with ablations.

A minimal future API might be::

    def distill_teacher_to_checkpoint(
        *,
        teacher: str,
        student_ckpt: Path,
        out: Path,
        games: int,
        seed: int,
    ) -> None: ...
"""

from __future__ import annotations


def distill_teacher_stub() -> None:
    """Placeholder until distillation pipeline is wired to the trainer."""

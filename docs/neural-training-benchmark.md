# Neural RL training throughput

Use `dbreaker benchmark-neural` to measure wall time for one `train_self_play` pass, split into:

- **rollout_seconds** — trajectory collection (simulation + policy sampling)
- **ppo_update_seconds** — tensor prep, batched policy/value re-evaluation, and Adam steps

For apples-to-apples comparisons (same step count and rewards), pass `**--torch-seed`** so PyTorch initialization and sampling match between runs. Environment RNG still follows `--seed` per game (`seed + game_index`).

## Optimizations in this codebase

1. **Batched PPO re-evaluation** — `evaluate_action_indices` runs padded chunk forwards instead of one forward per timestep (see `PolicyValueNetwork.forward_batch_padded`).
2. **Lean rollouts** — ML trajectory collection uses `Game.new(..., record_transitions=False)` so `Game.step` skips per-step state digests and action/event logs (game semantics unchanged).
3. **Seat lookup** — `collect_training_trajectory` maps `player_id` → seat with a dict instead of `list.index` each step.

## Example snapshot (developer machine; use your own numbers)

With `--games 3 --players 4 --seed 1 --max-turns 30 --max-self-play-steps 2000 --update-epochs 2 --torch-seed 0`, a typical run reports on the order of **~3.4k training steps/sec** total; rollout time is usually the larger share of wall time. Re-run `benchmark-neural` after changes to confirm rollout vs PPO split.
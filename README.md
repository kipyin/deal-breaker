# Deal Breaker

A small Python research platform for Monopoly Deal-style game engines and AI
strategy experiments.

Use it to play in the terminal, script games, run self-play tournaments, measure
simulator throughput, train a small checkpoint-backed neural policy, and inspect
replay logs.

## Run

Requires Python 3.11+.

From the repo:

```bash
uv run dbreaker --help
```

For development and tests (includes linters and pytest):

```bash
uv sync --extra dev
uv run pytest
```

**Optional ML** (`train`, loading `neural:…` checkpoints) needs PyTorch:

```bash
uv sync --extra dev --extra ml
```

Or install on your `PATH`:

```bash
pip install -e .
# with neural training / inference:
pip install -e ".[ml]"
dbreaker --help
```

## Commands

### Play

```bash
# Play against AI opponents.
uv run dbreaker play --players 3

# Play a game against a trained AI.
uv run dbreaker play --players 4 \
  --ai-strategy neural:checkpoints/selfplay.pt

# Run a scripted human turn stream.
printf 'draw\nend\n' | uv run dbreaker play --commands - --output text

# Compare strategies through self-play (comma-separated strategy specs).
uv run dbreaker tournament --players 4 --games 100 \
  --strategies random,basic,aggressive,defensive

# Print a JSONL replay log.
uv run dbreaker replay runs/latest/games/game-1.jsonl
```

### Train

```bash
# Measure simulator throughput (seat rotation matches tournament).
uv run dbreaker benchmark --games 500 --output text
uv run dbreaker benchmark --games 500 --output json

# Train a neural checkpoint (requires ML extra).
uv run dbreaker train --players 4 --games 20 \
  --checkpoint-out checkpoints/selfplay.pt

# Or train one checkpoint per player count.
uv run dbreaker rl-search --players 2,3,4,5 --games-per-run 10

# Evaluate a candidate vs a baseline (e.g. neural checkpoint vs basic).
uv run dbreaker evaluate --candidate neural:checkpoints/selfplay.pt --baseline basic
```

### Strategy specs

Built-in names include `random`, `basic`, `aggressive`, `defensive`,
`set_completion`, and `omniscient`. For checkpoint policies, use
`neural:/path/to/checkpoint.pt` (after `pip install -e ".[ml]"` or
`uv sync --extra ml`).

Run `uv run dbreaker <command> --help` for command-specific options.

## Inside

- `dbreaker.engine`: rules, cards, turns, payments, and game state.
- `dbreaker.strategies`: random, heuristic, aggressive, defensive, set-completion,
  omniscient baseline, and optional neural checkpoint strategies.
- `dbreaker.ml`: feature encoding, policy-value model, trajectories, checkpoints,
  and PPO-style self-play training.
- `dbreaker.experiments`: self-play runners, tournaments, Elo-style ratings,
  reports, and benchmarks.
- `dbreaker.replay`: JSONL event logs for replay and debugging.
- `tests`: coverage for engine behavior, CLI flows, strategies, experiments,
  replay, and ML paths.

## License

Apache-2.0; see [LICENSE](LICENSE).

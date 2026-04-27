# Deal Breaker

A small Python research platform for Monopoly Deal-style game engines and AI
strategy experiments.

Use it to play in the terminal, script games, run self-play tournaments, measure
simulator throughput, and inspect replay logs.

## Run

Requires Python 3.11+.

From the repo:

```bash
uv run dbreaker --help
```

Or install it on your `PATH`:

```bash
pip install -e .
dbreaker --help
```

## Commands

```bash
# Play against AI opponents.
uv run dbreaker play --players 3

# Run a scripted human turn stream.
printf 'draw\nend\n' | uv run dbreaker play --commands - --output text

# Compare strategies through self-play.
uv run dbreaker tournament --players 4 --games 100 --strategies random,basic,aggressive,defensive

# Measure simulator throughput.
uv run dbreaker benchmark --games 500 --output text
uv run dbreaker benchmark --games 500 --output json

# Print a JSONL replay log.
uv run dbreaker replay runs/latest/games/game-1.jsonl
```

Run `uv run dbreaker <command> --help` for command-specific options.

## Inside

- `dbreaker.engine`: rules, cards, turns, payments, and game state.
- `dbreaker.strategies`: random, heuristic, aggressive, defensive, set-completion,
  and omniscient baseline strategies.
- `dbreaker.experiments`: self-play runners, tournaments, Elo-style ratings,
  reports, and benchmarks.
- `dbreaker.replay`: JSONL event logs for replay and debugging.
- `tests`: coverage for engine behavior, CLI flows, strategies, experiments, and
  replay.

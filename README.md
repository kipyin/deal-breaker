# Monopoly Deal AI Research Platform

Python + terminal research platform for Monopoly Deal-style game engine experiments,
self-play tournaments, strategy comparison, replay, and debug logs.

## Commands

```bash
uv run dbreaker --help
uv run dbreaker play --players 3
uv run dbreaker tournament --players 4 --games 100
uv run dbreaker replay runs/latest/games/game-1.jsonl
```

## Playing in the terminal (`dbreaker play`)

- **You are always P1.** Other seats (P2, …) use the AI strategy from `--ai-strategy` (default `basic`).
- The board shows your **hand and bank** with each card as `Name [card_id]`. **Shortcuts and menus use `card_id`** — match what you see in brackets.
- **Choose an action** from the numbered list, or pick **Type a shortcut command** for typed commands (see **Show shortcut help** in the menu for examples).
- If a shortcut is invalid or not legal, you’ll see an error and can try again or return to the menu with an empty shortcut line.
- **AI turns** print a one-line summary of the action, then event messages.
- Requires **Python 3.11+**. With `uv`, use `uv run …` from the repo; otherwise install the package (e.g. `pip install -e .`) so `dbreaker` is on your `PATH`.

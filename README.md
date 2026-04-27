# Monopoly Deal AI Research Platform

Python + terminal research platform for Monopoly Deal-style game engine experiments,
self-play tournaments, strategy comparison, replay, and debug logs.

## Commands

```bash
uv run dbreaker --help
uv run dbreaker play --players 3
printf 'draw\nend\n' | uv run dbreaker play --commands - --output text
uv run dbreaker tournament --players 4 --games 100
uv run dbreaker replay runs/latest/games/game-1.jsonl
```

## Playing in the terminal (`dbreaker play`)

- **You are always P1.** Other seats (P2, …) use the AI strategy from `--ai-strategy` (default `basic`).
- The **board** is shown with [Rich](https://github.com/Textualize/rich) tables (status, hand, bank, your properties, opponents). The previous wall of “Legal actions” is only used where tools/tests ask for a plain text dump; during play you pick actions from the menu, not a duplicate list.
- **Shortcuts and menus use `card_id`** — it matches the bracketed id on the board. For a **card** that can be used in more than one way (e.g. bank and play the same property), you first pick the card row, then a second menu lists those uses, plus **View card details** and **Back**.
- For **payment** and other all-flat cases, the menu is a single numbered list of options (same as before, without repeating the whole list above the board).
- **Choose an action** from the menus, or pick **Type a shortcut command** (see **Show shortcut help** in the menu for examples). **View card details** shows rent ladder, set size, wild colors, etc., for cards in your hand, bank, or your property table.
- If a shortcut is invalid or not legal, you’ll see an error and can try again or return to the menu with an empty shortcut line.
- **AI turns** print a one-line summary of the action, then event messages.
- Requires **Python 3.11+**. With `uv`, use `uv run …` from the repo; otherwise install the package (e.g. `pip install -e .`) so `dbreaker` is on your `PATH`.

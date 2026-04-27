from __future__ import annotations

import json
import sys
from dataclasses import asdict
from typing import Literal, TextIO

from rich.console import Console

from dbreaker.cli.action_labels import format_action_label
from dbreaker.cli.commands import format_shortcut_help, legal_action_for_command
from dbreaker.cli.prompts import prompt_human_action
from dbreaker.cli.renderer import (
    build_card_name_map,
    format_ai_turn_header,
    render_events,
    render_observation_rich,
)
from dbreaker.engine.actions import Action, EndTurn
from dbreaker.engine.events import GameEvent
from dbreaker.engine.game import Game
from dbreaker.strategies.registry import default_registry


def run_interactive_play(players: int, ai_strategy: str = "basic") -> None:
    game = Game.new(player_count=players)
    registry = default_registry()
    console = Console()
    ai_players = {
        player_id: registry.create(ai_strategy) for player_id in game.state.player_order[1:]
    }

    while not game.is_terminal():
        player_id = game.active_player_id
        legal_actions = game.legal_actions(player_id)
        if player_id in ai_players:
            observation = game.observation_for(player_id)
            decision = ai_players[player_id].choose_action(observation, legal_actions)
            result = game.step(player_id, decision.action)
            name_by_id = build_card_name_map(observation)
            print(format_ai_turn_header(player_id, decision.action, name_by_id=name_by_id))
            print(render_events(result.events))
            continue

        observation = game.observation_for(player_id)
        console.print(render_observation_rich(observation))
        action = prompt_human_action(player_id, legal_actions, observation)
        result = game.step(player_id, action)
        print(render_events(result.events))


def run_non_interactive_demo(players: int) -> Game:
    game = Game.new(player_count=players)
    while not game.is_terminal() and game.state.turn <= players:
        game.step(game.state.current_player_id, EndTurn())
    return game


def _read_next_command(f: TextIO) -> str | None:
    """Read next non-empty, non-comment line, or return None on EOF."""
    while True:
        line = f.readline()
        if line == "":
            return None
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped


def _legal_action_labels(
    legal_actions: list[Action], name_by_id: dict[str, str]
) -> list[str]:
    return [format_action_label(a, name_by_id=name_by_id) for a in legal_actions]


def _json_dumps(data: object) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


def _events_payload(events: list[GameEvent]) -> list[dict[str, object]]:
    return [asdict(e) for e in events]


def run_scripted_play(
    players: int,
    ai_strategy: str,
    command_source: TextIO,
    *,
    output: Literal["text", "jsonl"] = "text",
    seed: int | None = None,
) -> int:
    """Run a game from ``command_source`` (one shortcut line per human turn).

    Returns 0 on normal end, 1 on error.
    """
    game = Game.new(player_count=players, seed=seed)
    registry = default_registry()
    ai_players = {
        player_id: registry.create(ai_strategy) for player_id in game.state.player_order[1:]
    }

    def fail(message: str, *, legal: list[str] | None = None) -> int:
        example = "uv run dbreaker play --players 2 --commands - --output text"
        if seed is not None:
            example = f"uv run dbreaker play --seed {seed} --players 2 --commands - --output text"
        if output == "jsonl":
            err_obj: dict[str, object] = {
                "type": "error",
                "message": message,
                "example": f"printf 'draw\\nend\\n' | {example}",
            }
            if legal is not None:
                err_obj["legal_actions"] = legal
            print(_json_dumps(err_obj), file=sys.stdout, flush=True)
        else:
            print(f"Error: {message}", file=sys.stderr)
            if legal is not None:
                n = len(legal)
                show = legal[:20]
                more = f" ... ({n} total)" if n > 20 else ""
                print(
                    f"  Legal actions ({n}): {show}{more}",
                    file=sys.stderr,
                )
            print("  " + format_shortcut_help().split("\n")[0], file=sys.stderr)
            print(f"  Example: {example}", file=sys.stderr)
        return 1

    while not game.is_terminal():
        player_id = game.active_player_id
        legal_actions = game.legal_actions(player_id)
        observation = game.observation_for(player_id)
        name_by_id = build_card_name_map(observation)
        if player_id in ai_players:
            turn_for_log = observation.turn
            decision = ai_players[player_id].choose_action(observation, legal_actions)
            result = game.step(player_id, decision.action)
            if output == "text":
                print(
                    format_ai_turn_header(player_id, decision.action, name_by_id=name_by_id)
                )
                print(render_events(result.events))
            else:
                print(
                    _json_dumps(
                        {
                            "type": "ai_step",
                            "turn": turn_for_log,
                            "player": player_id,
                            "action": format_action_label(
                                decision.action, name_by_id=name_by_id
                            ),
                            "events": _events_payload(result.events),
                        }
                    ),
                    flush=True,
                )
            continue

        legal_labels = _legal_action_labels(legal_actions, name_by_id)
        human_turn = observation.turn
        if output == "jsonl":
            print(
                _json_dumps(
                    {
                        "type": "legal_state",
                        "turn": human_turn,
                        "player": player_id,
                        "legal_actions": legal_labels,
                    }
                ),
                flush=True,
            )

        command_line = _read_next_command(command_source)
        if command_line is None:
            return fail(
                "end of command stream (need another line for human input)",
                legal=legal_labels,
            )

        try:
            action = legal_action_for_command(command_line, legal_actions)
        except ValueError as exc:
            return fail(
                f"{command_line!r}: {exc}",
                legal=legal_labels,
            )

        result = game.step(player_id, action)
        if output == "text":
            print(f"{player_id}> {command_line}")
            print(render_events(result.events))
        else:
            print(
                _json_dumps(
                    {
                        "type": "human_step",
                        "turn": human_turn,
                        "player": player_id,
                        "command": command_line,
                        "events": _events_payload(result.events),
                    }
                ),
                flush=True,
            )

    if output == "jsonl":
        print(
            _json_dumps(
                {
                    "type": "game_over",
                    "winner": game.state.winner_id,
                    "turn": game.state.turn,
                }
            ),
            flush=True,
        )
    else:
        w = game.state.winner_id
        print("Game over." + (f" Winner: {w}." if w else ""))
    return 0

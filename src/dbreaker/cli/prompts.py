from __future__ import annotations

import questionary
from questionary import Choice

from dbreaker.cli.action_labels import format_action_label
from dbreaker.cli.commands import format_shortcut_help, parse_command
from dbreaker.cli.renderer import build_card_name_map
from dbreaker.engine.actions import Action, PayWithAssets
from dbreaker.engine.observation import Observation

COMMAND_SENTINEL = "__shortcut_command__"
COMMAND_HELP_SENTINEL = "__shortcut_help__"


def build_action_choices(
    legal_actions: list[Action],
    *,
    name_by_id: dict[str, str] | None = None,
) -> list[Choice]:
    names = name_by_id or {}
    choices = [
        Choice(
            title=f"{index}. {format_action_label(action, name_by_id=names)}",
            value=action,
        )
        for index, action in enumerate(legal_actions, start=1)
    ]
    choices.append(Choice(title="Type a shortcut command", value=COMMAND_SENTINEL))
    choices.append(Choice(title="Show shortcut help", value=COMMAND_HELP_SENTINEL))
    return choices


def resolve_action_selection(
    selection: Action | str,
    legal_actions: list[Action],
    *,
    command_text: str | None = None,
) -> Action:
    if isinstance(selection, Action):
        if selection not in legal_actions:
            raise ValueError("selected action is not legal")
        return selection
    if selection == COMMAND_SENTINEL:
        if not command_text:
            raise ValueError("shortcut command text is required")
        action = parse_command(command_text)
        legal_action = _matching_legal_action(action, legal_actions)
        if legal_action is None:
            raise ValueError("shortcut command is not legal")
        return legal_action
    raise ValueError(f"unsupported action selection: {selection}")


def prompt_human_action(
    player_id: str,
    legal_actions: list[Action],
    observation: Observation,
) -> Action:
    name_by_id = build_card_name_map(observation)
    while True:
        selection = questionary.select(
            f"{player_id}, choose an action",
            choices=build_action_choices(legal_actions, name_by_id=name_by_id),
            use_shortcuts=True,
        ).ask()
        if selection is None:
            raise KeyboardInterrupt
        if selection == COMMAND_HELP_SENTINEL:
            print(format_shortcut_help())
            continue
        if selection == COMMAND_SENTINEL:
            while True:
                command_text = questionary.text(
                    "Shortcut command (leave empty to return to menu)"
                ).ask()
                if command_text is None:
                    raise KeyboardInterrupt
                if not command_text.strip():
                    break
                try:
                    action = parse_command(command_text)
                    legal_action = _matching_legal_action(action, legal_actions)
                    if legal_action is None:
                        print("Could not use shortcut: shortcut command is not legal")
                        continue
                    return legal_action
                except ValueError as exc:
                    print(f"Could not use shortcut: {exc}")
            continue
        if isinstance(selection, Action):
            if selection not in legal_actions:
                print("Could not use shortcut: selected action is not legal")
                continue
            return selection
        raise ValueError(f"unsupported action selection: {selection}")


def _matching_legal_action(action: Action, legal_actions: list[Action]) -> Action | None:
    if action in legal_actions:
        return action
    if isinstance(action, PayWithAssets):
        requested = sorted(action.card_ids)
        for legal_action in legal_actions:
            if (
                isinstance(legal_action, PayWithAssets)
                and sorted(legal_action.card_ids) == requested
            ):
                return legal_action
    return None

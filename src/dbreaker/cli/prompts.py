from __future__ import annotations

import questionary
from questionary import Choice
from questionary.prompts.common import InquirerControl, Separator
from rich.console import Console

from dbreaker.cli.action_labels import card_display
from dbreaker.cli.action_menu import (
    BACK,
    VIEW_DETAILS,
    CardGroupPick,
    actions_for_card_group,
    build_flat_action_choices,
    build_submenu_choices,
    build_top_level_choices,
    is_payment_only,
)
from dbreaker.cli.commands import format_shortcut_help, parse_command
from dbreaker.cli.renderer import build_card_name_map, build_cards_index, card_details_rich
from dbreaker.engine.actions import Action, PayWithAssets
from dbreaker.engine.observation import Observation

COMMAND_SENTINEL = "__shortcut_command__"
COMMAND_HELP_SENTINEL = "__shortcut_help__"


def _can_use_questionary_shortcuts(choices: list[Choice]) -> bool:
    real_choice_count = sum(1 for choice in choices if not isinstance(choice, Separator))
    return real_choice_count <= len(InquirerControl.SHORTCUT_KEYS)


def _with_shortcut_choices(choices: list[Choice]) -> list[Choice]:
    return [
        *choices,
        Choice(title="Type a shortcut command", value=COMMAND_SENTINEL),
        Choice(title="Show shortcut help", value=COMMAND_HELP_SENTINEL),
    ]


def build_action_choices(
    legal_actions: list[Action],
    *,
    name_by_id: dict[str, str] | None = None,
) -> list[Choice]:
    """Flat numbered legal actions plus shortcut entries (tests and building block)."""
    return _with_shortcut_choices(
        build_flat_action_choices(legal_actions, name_by_id=name_by_id or {})
    )


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


def _prompt_shortcut_command(legal_actions: list[Action]) -> Action | None:
    while True:
        command_text = questionary.text(
            "Shortcut command (leave empty to return to menu)"
        ).ask()
        if command_text is None:
            raise KeyboardInterrupt
        if not command_text.strip():
            return None
        try:
            action = parse_command(command_text)
            legal_action = _matching_legal_action(action, legal_actions)
            if legal_action is None:
                print("Could not use shortcut: shortcut command is not legal")
                continue
            return legal_action
        except ValueError as exc:
            print(f"Could not use shortcut: {exc}")


def prompt_human_action(
    player_id: str,
    legal_actions: list[Action],
    observation: Observation,
) -> Action:
    name_by_id = build_card_name_map(observation)
    cards_index = build_cards_index(observation)
    console = Console()
    while True:
        if is_payment_only(legal_actions):
            choices = _with_shortcut_choices(
                build_flat_action_choices(legal_actions, name_by_id=name_by_id)
            )
        else:
            choices = _with_shortcut_choices(
                build_top_level_choices(legal_actions, name_by_id=name_by_id)
            )
        selection = questionary.select(
            f"{player_id}, choose an action",
            choices=choices,
            use_shortcuts=_can_use_questionary_shortcuts(choices),
        ).ask()
        if selection is None:
            raise KeyboardInterrupt
        if selection == COMMAND_HELP_SENTINEL:
            print(format_shortcut_help())
            continue
        if selection == COMMAND_SENTINEL:
            picked = _prompt_shortcut_command(legal_actions)
            if picked is not None:
                return picked
            continue
        if isinstance(selection, CardGroupPick):
            card_id = selection.card_id
            group_actions = actions_for_card_group(card_id, legal_actions)
            while True:
                sub_choices = build_submenu_choices(
                    card_id, group_actions, name_by_id=name_by_id
                )
                sel2 = questionary.select(
                    f"{player_id} — {card_display(card_id, name_by_id)}",
                    choices=sub_choices,
                    use_shortcuts=_can_use_questionary_shortcuts(sub_choices),
                ).ask()
                if sel2 is None:
                    raise KeyboardInterrupt
                if sel2 == BACK:
                    break
                if sel2 == VIEW_DETAILS:
                    card = cards_index.get(card_id)
                    if card is not None:
                        console.print(card_details_rich(card))
                    else:
                        nm = name_by_id.get(card_id, "?")
                        console.print(
                            f"[dim]id[/] {card_id}  [dim]name[/] {nm}\n"
                            "[dim](Card object not in your hand, bank, or your property piles.)[/]"
                        )
                    continue
                if isinstance(sel2, Action):
                    if sel2 not in legal_actions:
                        print("Could not use selection: action is not legal")
                        continue
                    return sel2
            continue
        if isinstance(selection, Action):
            if selection not in legal_actions:
                print("Could not use selection: selected action is not legal")
                continue
            return selection
        raise ValueError(f"unsupported action selection: {selection}")

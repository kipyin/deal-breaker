from __future__ import annotations

import questionary
from questionary import Choice
from questionary.prompts.common import InquirerControl, Separator
from rich.console import Console

from dbreaker.cli.action_labels import card_display
from dbreaker.cli.action_menu import (
    BACK,
    VIEW_DETAILS,
    ActionCategoryPick,
    CardGroupPick,
    PaymentCategoryPick,
    actions_for_card_group,
    build_action_category_picker_choices,
    build_flat_action_choices,
    build_payment_category_picker_choices,
    build_submenu_choices,
    build_top_level_choices,
    group_legal_by_action_category,
    group_payments_by_category,
    is_payment_only,
    should_use_action_category_menu,
    should_use_payment_category_menu,
)
from dbreaker.cli.commands import (
    format_shortcut_help_topic,
    matching_legal_action,
    parse_command,
    short_help_topic_choices,
)
from dbreaker.cli.nested_pickers import (
    run_nested_play_action_picker,
    run_nested_rent_picker,
    should_nested_play_action_wizard,
    should_nested_rent_wizard,
)
from dbreaker.cli.renderer import build_card_name_map, build_cards_index, card_details_rich
from dbreaker.engine.actions import Action, PayWithAssets, PlayRent
from dbreaker.engine.cards import Card
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


def _with_back_shortcut_choices(choices: list[Choice]) -> list[Choice]:
    return [
        *choices,
        Choice(title="Back", value=BACK),
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
        legal_action = matching_legal_action(action, legal_actions)
        if legal_action is None:
            raise ValueError("shortcut command is not legal")
        return legal_action
    raise ValueError(f"unsupported action selection: {selection}")


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
            legal_action = matching_legal_action(action, legal_actions)
            if legal_action is None:
                print("Could not use shortcut: shortcut command is not legal")
                continue
            return legal_action
        except ValueError as exc:
            print(f"Could not use shortcut: {exc}")


def _prompt_shortcut_help_menu() -> None:
    items = short_help_topic_choices()
    choices: list[Choice] = [
        Choice(title=title, value=key) for key, title in items
    ]
    choices.append(Choice(title="Cancel", value="__cancel__"))
    picked = questionary.select(
        "Shortcut help (choose a topic)",
        choices=choices,
        use_shortcuts=_can_use_questionary_shortcuts(choices),
    ).ask()
    if picked is None or picked == "__cancel__":
        return
    if isinstance(picked, str):
        print(format_shortcut_help_topic(picked))


def _prompt_payment_only(
    player_id: str,
    legal_actions: list[Action],
    name_by_id: dict[str, str],
    cards_index: dict[str, Card],
) -> Action:
    pay_list = [a for a in legal_actions if isinstance(a, PayWithAssets)]
    typed_index = cards_index

    if not should_use_payment_category_menu(legal_actions, typed_index):
        choices = _with_shortcut_choices(
            build_flat_action_choices(pay_list, name_by_id=name_by_id)
        )
        while True:
            selection = questionary.select(
                f"{player_id}, choose an action",
                choices=choices,
                use_shortcuts=_can_use_questionary_shortcuts(choices),
            ).ask()
            if selection is None:
                raise KeyboardInterrupt
            if selection == COMMAND_HELP_SENTINEL:
                _prompt_shortcut_help_menu()
                continue
            if selection == COMMAND_SENTINEL:
                picked = _prompt_shortcut_command(legal_actions)
                if picked is not None:
                    return picked
                continue
            if isinstance(selection, PayWithAssets):
                if selection not in legal_actions:
                    print("Could not use selection: selected action is not legal")
                    continue
                return selection
            raise ValueError(f"unsupported payment selection: {selection}")

    while True:
        c1 = _with_shortcut_choices(
            build_payment_category_picker_choices(pay_list, typed_index)
        )
        s1 = questionary.select(
            f"{player_id}, choose how to pay",
            choices=c1,
            use_shortcuts=_can_use_questionary_shortcuts(c1),
        ).ask()
        if s1 is None:
            raise KeyboardInterrupt
        if s1 == COMMAND_HELP_SENTINEL:
            _prompt_shortcut_help_menu()
            continue
        if s1 == COMMAND_SENTINEL:
            picked = _prompt_shortcut_command(legal_actions)
            if picked is not None:
                return picked
            continue
        if isinstance(s1, PaymentCategoryPick):
            g = group_payments_by_category(pay_list, typed_index)
            sub_actions = g.get(s1.key, [])
            if not sub_actions:
                continue
            while True:
                c2 = _with_back_shortcut_choices(
                    build_flat_action_choices(sub_actions, name_by_id=name_by_id)
                )
                s2 = questionary.select(
                    f"{player_id}, choose payment — {s1.key}",
                    choices=c2,
                    use_shortcuts=_can_use_questionary_shortcuts(c2),
                ).ask()
                if s2 is None:
                    raise KeyboardInterrupt
                if s2 == COMMAND_HELP_SENTINEL:
                    _prompt_shortcut_help_menu()
                    continue
                if s2 == COMMAND_SENTINEL:
                    picked0 = _prompt_shortcut_command(legal_actions)
                    if picked0 is not None:
                        return picked0
                    continue
                if s2 == BACK:
                    break
                if isinstance(s2, PayWithAssets):
                    if s2 not in legal_actions:
                        print("Could not use selection: selected action is not legal")
                        continue
                    return s2
                raise ValueError(f"unsupported payment pick: {s2}")
            continue
        raise ValueError(f"unsupported payment selection: {s1}")


def _run_card_group_submenu(
    player_id: str,
    card_id: str,
    group_actions: list[Action],
    legal_actions: list[Action],
    name_by_id: dict[str, str],
    cards_index: dict[str, Card],
    console: Console,
) -> Action | None:
    """Returns a chosen Action or None if user backed out to the parent menu."""
    while True:
        if should_nested_rent_wizard(group_actions) and all(
            isinstance(a, PlayRent) for a in group_actions
        ):
            rent_act = [
                a for a in group_actions if isinstance(a, PlayRent)
            ]
            picked = run_nested_rent_picker(player_id, rent_act, name_by_id)
            if picked is not None:
                return picked
            continue

        if should_nested_play_action_wizard(group_actions, cards_index):
            picked = run_nested_play_action_picker(
                player_id, group_actions, name_by_id, cards_index
            )
            if picked is not None:
                return picked
            continue

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
            return None
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


def prompt_human_action(
    player_id: str,
    legal_actions: list[Action],
    observation: Observation,
) -> Action:
    name_by_id = build_card_name_map(observation)
    cards_index = build_cards_index(observation)
    console = Console()

    if is_payment_only(legal_actions):
        return _prompt_payment_only(
            player_id, legal_actions, name_by_id, cards_index
        )

    use_categories = should_use_action_category_menu(legal_actions, name_by_id=name_by_id)

    while True:
        if use_categories:
            c0 = _with_shortcut_choices(
                build_action_category_picker_choices(legal_actions)
            )
            prompt_title = f"{player_id}, choose action type"
            selection0 = questionary.select(
                prompt_title,
                choices=c0,
                use_shortcuts=_can_use_questionary_shortcuts(c0),
            ).ask()
            if selection0 is None:
                raise KeyboardInterrupt
            if selection0 == COMMAND_HELP_SENTINEL:
                _prompt_shortcut_help_menu()
                continue
            if selection0 == COMMAND_SENTINEL:
                picked = _prompt_shortcut_command(legal_actions)
                if picked is not None:
                    return picked
                continue
            if isinstance(selection0, ActionCategoryPick):
                g = group_legal_by_action_category(legal_actions)
                subset = g.get(selection0.key, [])
                if not subset:
                    continue
                while True:
                    choices = _with_back_shortcut_choices(
                        build_top_level_choices(subset, name_by_id=name_by_id)
                    )
                    s_in = questionary.select(
                        f"{player_id}, choose an action — {selection0.key}",
                        choices=choices,
                        use_shortcuts=_can_use_questionary_shortcuts(choices),
                    ).ask()
                    if s_in is None:
                        raise KeyboardInterrupt
                    if s_in == COMMAND_HELP_SENTINEL:
                        _prompt_shortcut_help_menu()
                        continue
                    if s_in == COMMAND_SENTINEL:
                        picked1 = _prompt_shortcut_command(legal_actions)
                        if picked1 is not None:
                            return picked1
                        continue
                    if s_in == BACK:
                        break
                    if isinstance(s_in, CardGroupPick):
                        card_id = s_in.card_id
                        group_actions = actions_for_card_group(card_id, subset)
                        result = _run_card_group_submenu(
                            player_id,
                            card_id,
                            group_actions,
                            legal_actions,
                            name_by_id,
                            cards_index,
                            console,
                        )
                        if result is not None:
                            return result
                        continue
                    if isinstance(s_in, Action):
                        if s_in not in legal_actions:
                            print("Could not use selection: selected action is not legal")
                            continue
                        return s_in
                continue
            raise ValueError(f"unsupported category selection: {selection0}")

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
            _prompt_shortcut_help_menu()
            continue
        if selection == COMMAND_SENTINEL:
            picked = _prompt_shortcut_command(legal_actions)
            if picked is not None:
                return picked
            continue
        if isinstance(selection, CardGroupPick):
            card_id = selection.card_id
            group_actions = actions_for_card_group(card_id, legal_actions)
            result = _run_card_group_submenu(
                player_id,
                card_id,
                group_actions,
                legal_actions,
                name_by_id,
                cards_index,
                console,
            )
            if result is not None:
                return result
            continue
        if isinstance(selection, Action):
            if selection not in legal_actions:
                print("Could not use selection: selected action is not legal")
                continue
            return selection
        raise ValueError(f"unsupported action selection: {selection}")

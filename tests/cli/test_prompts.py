import pytest
from questionary import Choice

from dbreaker.cli.prompts import (
    COMMAND_HELP_SENTINEL,
    COMMAND_SENTINEL,
    _can_use_questionary_shortcuts,
    build_action_choices,
    resolve_action_selection,
)
from dbreaker.engine.actions import BankCard, EndTurn, PayWithAssets


def test_build_action_choices_include_numbered_actions_shortcut_and_help() -> None:
    actions = [BankCard(card_id="money-1"), EndTurn()]

    choices = build_action_choices(actions)

    assert choices[0].title == "1. Bank money-1"
    assert choices[0].value == actions[0]
    assert choices[-2].value == COMMAND_SENTINEL
    assert choices[-1].value == COMMAND_HELP_SENTINEL


def test_build_action_choices_use_card_names_when_provided() -> None:
    actions = [BankCard(card_id="money-1"), EndTurn()]

    choices = build_action_choices(actions, name_by_id={"money-1": "$1"})

    assert choices[0].title == "1. Bank $1 [money-1]"


def test_questionary_shortcuts_disabled_for_large_menus() -> None:
    assert _can_use_questionary_shortcuts(
        [Choice(title=str(i), value=i) for i in range(36)]
    )
    assert not _can_use_questionary_shortcuts(
        [Choice(title=str(i), value=i) for i in range(37)]
    )


def test_resolve_action_selection_returns_selected_action() -> None:
    action = EndTurn()

    assert resolve_action_selection(action, [action]) == action


def test_resolve_action_selection_parses_shortcut_command() -> None:
    action = resolve_action_selection(
        COMMAND_SENTINEL,
        [BankCard(card_id="money-1")],
        command_text="bank money-1",
    )

    assert action == BankCard(card_id="money-1")


def test_resolve_action_selection_rejects_illegal_shortcut_command() -> None:
    with pytest.raises(ValueError, match="not legal"):
        resolve_action_selection(
            COMMAND_SENTINEL,
            [EndTurn()],
            command_text="bank money-1",
        )


def test_resolve_action_selection_canonicalizes_payment_shortcut_order() -> None:
    legal_action = PayWithAssets(card_ids=("money-1", "property-1"))

    action = resolve_action_selection(
        COMMAND_SENTINEL,
        [legal_action],
        command_text="pay property-1 money-1",
    )

    assert action == legal_action


def test_resolve_action_selection_requires_shortcut_text() -> None:
    with pytest.raises(ValueError, match="shortcut command"):
        resolve_action_selection(COMMAND_SENTINEL, [])

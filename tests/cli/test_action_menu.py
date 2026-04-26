from dbreaker.cli.action_menu import (
    BACK,
    VIEW_DETAILS,
    CardGroupPick,
    actions_for_card_group,
    build_submenu_choices,
    build_top_level_choices,
    is_payment_only,
)
from dbreaker.engine.actions import (
    BankCard,
    EndTurn,
    PayWithAssets,
    PlayProperty,
)
from dbreaker.engine.cards import PropertyColor


def test_is_payment_only() -> None:
    assert is_payment_only([PayWithAssets(card_ids=("a",))])
    assert not is_payment_only([PayWithAssets(card_ids=("a",)), EndTurn()])


def test_multi_use_card_row_is_card_group_pick() -> None:
    actions = [
        BankCard("yellow-3"),
        PlayProperty("yellow-3", color=PropertyColor.YELLOW),
    ]
    choices = build_top_level_choices(
        actions,
        name_by_id={"yellow-3": "Marvin Gardens"},
    )
    picks = [c.value for c in choices if isinstance(c.value, CardGroupPick)]
    assert picks == [CardGroupPick(card_id="yellow-3")]


def test_single_use_card_is_one_click_not_grouped() -> None:
    actions = [BankCard("money-1-1"), EndTurn()]
    choices = build_top_level_choices(
        actions,
        name_by_id={"money-1-1": "$1"},
    )
    assert not any(isinstance(c.value, CardGroupPick) for c in choices)
    values = {c.value for c in choices if isinstance(c.value, (BankCard, EndTurn))}
    assert values == {BankCard("money-1-1"), EndTurn()}


def test_submenu_includes_back_and_view_details() -> None:
    actions = [BankCard("x"), PlayProperty("x", color=PropertyColor.RED)]
    sub = build_submenu_choices("x", actions, name_by_id={"x": "Test"})

    assert [c.value for c in sub][-1] is BACK
    assert [c.value for c in sub][-2] is VIEW_DETAILS


def test_actions_for_card_group_filters() -> None:
    actions = [BankCard("a"), BankCard("b"), EndTurn()]
    assert {a for a in actions_for_card_group("a", actions)} == {BankCard("a")}

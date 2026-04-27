from dbreaker.cli.action_menu import (
    BACK,
    VIEW_DETAILS,
    CardGroupPick,
    actions_for_card_group,
    build_submenu_choices,
    build_top_level_choices,
    group_payments_by_category,
    is_payment_only,
    payment_category,
    should_use_action_category_menu,
    should_use_payment_category_menu,
)
from dbreaker.engine.actions import (
    BankCard,
    EndTurn,
    PayWithAssets,
    PlayProperty,
)
from dbreaker.engine.cards import Card, CardKind, PropertyColor


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


def test_payment_category_bucketing() -> None:
    m1 = Card(id="m1", name="$1", kind=CardKind.MONEY, value=1)
    p1 = Card(
        id="p1",
        name="Ave",
        kind=CardKind.PROPERTY,
        value=1,
        color=PropertyColor.BLUE,
    )
    by_id = {"m1": m1, "p1": p1}
    assert payment_category(PayWithAssets(card_ids=()), by_id) == "nothing"
    assert payment_category(PayWithAssets(card_ids=("m1",)), by_id) == "bank"
    assert payment_category(PayWithAssets(card_ids=("p1",)), by_id) == "board"
    assert payment_category(PayWithAssets(card_ids=("m1", "p1")), by_id) == "mixed"


def test_should_use_payment_category_menu_multiple_buckets() -> None:
    m1 = Card(id="m1", name="$1", kind=CardKind.MONEY, value=1)
    p1 = Card(id="p1", name="Ave", kind=CardKind.PROPERTY, value=1, color=PropertyColor.BLUE)
    acts = [
        PayWithAssets(card_ids=("m1",)),
        PayWithAssets(card_ids=("p1",)),
    ]
    assert should_use_payment_category_menu(acts, {"m1": m1, "p1": p1})
    pays = [a for a in acts if isinstance(a, PayWithAssets)]
    g = group_payments_by_category(pays, {"m1": m1, "p1": p1})
    assert len(g["bank"]) == 1 and len(g["board"]) == 1


def test_should_use_action_category_menu_when_many_top_rows() -> None:
    actions = [BankCard(f"money-{i:02d}") for i in range(13)] + [EndTurn()]
    assert should_use_action_category_menu(actions, name_by_id={})

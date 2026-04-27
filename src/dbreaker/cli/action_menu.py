from __future__ import annotations

from dataclasses import dataclass

from questionary import Choice

from dbreaker.cli.action_labels import card_display, format_action_label
from dbreaker.engine.actions import (
    Action,
    BankCard,
    DiscardCard,
    DrawCards,
    EndTurn,
    PayWithAssets,
    PlayActionCard,
    PlayProperty,
    PlayRent,
    RearrangeProperty,
    RespondJustSayNo,
)
from dbreaker.engine.cards import Card, CardKind

VIEW_DETAILS = "__view_card_details__"
BACK = "__back__"


@dataclass(frozen=True, slots=True)
class CardGroupPick:
    """User chose a card that has more than one legal use."""

    card_id: str


@dataclass(frozen=True, slots=True)
class ActionCategoryPick:
    """User chose a top-level category for large non-payment menus."""

    key: str


@dataclass(frozen=True, slots=True)
class PaymentCategoryPick:
    """User chose a payment group (see ``payment_category``)."""

    key: str


# When top-level count exceeds this, show category picker first.
LARGE_TOP_LEVEL_CHOICE_THRESHOLD = 12


def primary_card_id(action: Action) -> str | None:
    """Key used to group card-scoped legal actions, or None if not groupable by card."""
    if isinstance(
        action,
        (
            BankCard,
            DiscardCard,
            PlayProperty,
            PlayRent,
            PlayActionCard,
            RearrangeProperty,
        ),
    ):
        return action.card_id
    if isinstance(action, RespondJustSayNo) and action.card_id is not None:
        return action.card_id
    return None


def is_payment_only(legal_actions: list[Action]) -> bool:
    return bool(legal_actions) and all(isinstance(a, PayWithAssets) for a in legal_actions)


def _action_sort_key(action: Action, name_by_id: dict[str, str]) -> str:
    return format_action_label(action, name_by_id=name_by_id).lower()


def _badges_for_actions(actions: list[Action]) -> str:
    tags: set[str] = set()
    for a in actions:
        if isinstance(a, BankCard):
            tags.add("bank")
        elif isinstance(a, DiscardCard):
            tags.add("discard")
        elif isinstance(a, PlayProperty):
            tags.add("play")
        elif isinstance(a, PlayRent):
            tags.add("rent")
        elif isinstance(a, PlayActionCard):
            tags.add("play")
        elif isinstance(a, RearrangeProperty):
            tags.add("move")
        elif isinstance(a, RespondJustSayNo):
            tags.add("respond")
    order = (
        "bank",
        "play",
        "rent",
        "discard",
        "move",
        "respond",
    )
    return " · ".join(t for t in order if t in tags)


def group_legal_actions(
    legal_actions: list[Action],
) -> tuple[dict[str, list[Action]], list[Action]]:
    grouped: dict[str, list[Action]] = {}
    ungrouped: list[Action] = []
    for action in legal_actions:
        card_id = primary_card_id(action)
        if card_id is None:
            ungrouped.append(action)
        else:
            grouped.setdefault(card_id, []).append(action)
    return grouped, ungrouped


def _sort_group_actions(actions: list[Action], name_by_id: dict[str, str]) -> list[Action]:
    return sorted(actions, key=lambda a: _action_sort_key(a, name_by_id))


def _split_multisingle(
    grouped: dict[str, list[Action]], name_by_id: dict[str, str]
) -> tuple[dict[str, list[Action]], list[Action]]:
    multi: dict[str, list[Action]] = {}
    single_flat: list[Action] = []
    def _group_order(item: tuple[str, list[Action]]) -> tuple[str, str]:
        cid, _ = item
        return (name_by_id.get(cid, cid).lower(), cid)

    for card_id, raw in sorted(grouped.items(), key=_group_order):
        actions = _sort_group_actions(raw, name_by_id)
        if len(actions) > 1:
            multi[card_id] = actions
        else:
            single_flat.append(actions[0])
    return multi, single_flat


def _card_group_title(card_id: str, actions: list[Action], name_by_id: dict[str, str]) -> str:
    line = card_display(card_id, name_by_id)
    badges = _badges_for_actions(actions)
    if badges:
        return f"{line}  —  {badges}"
    return line


def build_flat_action_choices(
    legal_actions: list[Action],
    *,
    name_by_id: dict[str, str] | None = None,
) -> list[Choice]:
    """Single-level menu: one row per action (for payment or other all-flat phases)."""
    names = name_by_id or {}
    order = sorted(legal_actions, key=lambda a: _action_sort_key(a, names))
    choices = [
        Choice(
            title=f"{index}. {format_action_label(action, name_by_id=names)}",
            value=action,
        )
        for index, action in enumerate(order, start=1)
    ]
    return choices


def build_top_level_choices(
    legal_actions: list[Action],
    *,
    name_by_id: dict[str, str],
) -> list[Choice]:
    """Build card-first top menu: multi-use cards, then one-click single actions, End turn last."""
    grouped, ungrouped = group_legal_actions(legal_actions)
    multi, single_from_groups = _split_multisingle(grouped, name_by_id)

    flat_actions: list[Action] = single_from_groups + ungrouped
    end_turns = [a for a in flat_actions if isinstance(a, EndTurn)]
    non_end = [a for a in flat_actions if not isinstance(a, EndTurn)]

    choices: list[Choice] = []
    index = 0

    def _multi_key(item: tuple[str, list[Action]]) -> tuple[str, str]:
        cid, _ = item
        return (name_by_id.get(cid, cid).lower(), cid)

    for card_id, actions in sorted(multi.items(), key=_multi_key):
        index += 1
        title = f"{index}. {_card_group_title(card_id, actions, name_by_id)}"
        choices.append(Choice(title=title, value=CardGroupPick(card_id=card_id)))

    for action in sorted(non_end, key=lambda a: _action_sort_key(a, name_by_id)):
        index += 1
        choices.append(
            Choice(
                title=f"{index}. {format_action_label(action, name_by_id=name_by_id)}",
                value=action,
            )
        )

    for end in end_turns:
        index += 1
        choices.append(
            Choice(
                title=f"{index}. {format_action_label(end, name_by_id=name_by_id)}",
                value=end,
            )
        )

    return choices


def build_submenu_choices(
    _card_id: str,
    actions: list[Action],
    *,
    name_by_id: dict[str, str],
) -> list[Choice]:
    """Second-level: concrete uses, view details, back. Pass ``card_id`` for call-site clarity."""
    ordered = _sort_group_actions(actions, name_by_id)
    choices: list[Choice] = []
    for index, action in enumerate(ordered, start=1):
        choices.append(
            Choice(
                title=f"{index}. {format_action_label(action, name_by_id=name_by_id)}",
                value=action,
            )
        )
    choices.append(Choice(title="View card details", value=VIEW_DETAILS))
    choices.append(Choice(title="Back", value=BACK))
    return choices


def actions_for_card_group(card_id: str, legal_actions: list[Action]) -> list[Action]:
    return [a for a in legal_actions if primary_card_id(a) == card_id]


def _card_by_id(cards: dict[str, Card], card_id: str) -> Card | None:
    return cards.get(card_id)


def payment_category(p: PayWithAssets, card_by_id: dict[str, Card]) -> str:
    """Bucketing key for a payment: ``nothing``, ``bank``, ``board``, or ``mixed``."""
    if not p.card_ids:
        return "nothing"
    has_money = False
    has_non_money = False
    for cid in p.card_ids:
        card = _card_by_id(card_by_id, cid)
        if card is None:
            has_non_money = True
            continue
        if card.kind == CardKind.MONEY:
            has_money = True
        else:
            has_non_money = True
    if has_money and has_non_money:
        return "mixed"
    if has_money and not has_non_money:
        return "bank"
    return "board"


def group_payments_by_category(
    legal_actions: list[PayWithAssets], card_by_id: dict[str, Card]
) -> dict[str, list[PayWithAssets]]:
    """Map payment category key -> list of legal ``PayWithAssets`` in that group."""
    grouped: dict[str, list[PayWithAssets]] = {
        "nothing": [],
        "bank": [],
        "board": [],
        "mixed": [],
    }
    for a in legal_actions:
        if not isinstance(a, PayWithAssets):
            continue
        grouped[payment_category(a, card_by_id)].append(a)
    return grouped


PAYMENT_CATEGORY_TITLES: dict[str, str] = {
    "nothing": "Pay with nothing (empty payment)",
    "bank": "Pay with money from bank only",
    "board": "Pay with on-table assets only (properties, buildings, …)",
    "mixed": "Pay with mixed (money and other assets)",
}


def should_use_payment_category_menu(
    legal_actions: list[Action], card_by_id: dict[str, Card]
) -> bool:
    """True when more than one payment group has at least one option."""
    if not legal_actions or not all(isinstance(a, PayWithAssets) for a in legal_actions):
        return False
    g = group_payments_by_category(
        [a for a in legal_actions if isinstance(a, PayWithAssets)], card_by_id
    )
    non_empty = sum(1 for v in g.values() if v)
    return non_empty > 1


def action_category_key(action: Action) -> str:
    if isinstance(action, DrawCards):
        return "draw"
    if isinstance(action, BankCard):
        return "bank"
    if isinstance(action, PlayProperty):
        return "play_property"
    if isinstance(action, PlayRent):
        return "rent"
    if isinstance(action, PlayActionCard):
        return "play_action"
    if isinstance(action, RearrangeProperty):
        return "rearrange"
    if isinstance(action, EndTurn):
        return "end_turn"
    if isinstance(action, DiscardCard):
        return "discard"
    if isinstance(action, RespondJustSayNo):
        return "respond"
    if isinstance(action, PayWithAssets):
        return "pay"
    return "other"


def action_category_order() -> list[str]:
    return [
        "draw",
        "bank",
        "play_property",
        "rent",
        "play_action",
        "rearrange",
        "discard",
        "end_turn",
        "respond",
        "pay",
        "other",
    ]


def action_category_label(key: str) -> str:
    return {
        "draw": "Draw",
        "bank": "Bank a card from hand",
        "play_property": "Play a property on the table",
        "rent": "Charge rent",
        "play_action": "Play an action card",
        "rearrange": "Move a property to another color",
        "discard": "Discard from hand",
        "end_turn": "End turn",
        "respond": "Respond to an effect",
        "pay": "Pay",
        "other": "Other",
    }[key]


def group_legal_by_action_category(
    legal_actions: list[Action],
) -> dict[str, list[Action]]:
    grouped: dict[str, list[Action]] = {k: [] for k in action_category_order()}
    for a in legal_actions:
        key = action_category_key(a)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(a)
    return grouped


def should_use_action_category_menu(
    legal_actions: list[Action], *, name_by_id: dict[str, str]
) -> bool:
    if is_payment_only(legal_actions) or not legal_actions:
        return False
    n = len(
        build_top_level_choices(legal_actions, name_by_id=name_by_id)
    )
    return n > LARGE_TOP_LEVEL_CHOICE_THRESHOLD


def build_action_category_picker_choices(
    legal_actions: list[Action],
) -> list[Choice]:
    """One row per non-empty action category, for the first level of a large main menu."""
    g = group_legal_by_action_category(legal_actions)
    choices: list[Choice] = []
    index = 0
    for key in action_category_order():
        bucket = g.get(key, [])
        if not bucket:
            continue
        index += 1
        choices.append(
            Choice(
                title=f"{index}. {action_category_label(key)} ({len(bucket)})",
                value=ActionCategoryPick(key=key),
            )
        )
    return choices


def build_payment_category_picker_choices(
    legal_actions: list[PayWithAssets], card_by_id: dict[str, Card]
) -> list[Choice]:
    """One row per non-empty payment group."""
    g = group_payments_by_category(legal_actions, card_by_id)
    choices: list[Choice] = []
    order = ("nothing", "bank", "board", "mixed")
    index = 0
    for key in order:
        bucket = g.get(key, [])
        if not bucket:
            continue
        index += 1
        label = PAYMENT_CATEGORY_TITLES.get(key, key)
        choices.append(
            Choice(
                title=f"{index}. {label} ({len(bucket)})",
                value=PaymentCategoryPick(key=key),
            )
        )
    return choices

from __future__ import annotations

from dataclasses import dataclass

from questionary import Choice

from dbreaker.cli.action_labels import card_display, format_action_label
from dbreaker.engine.actions import (
    Action,
    BankCard,
    DiscardCard,
    EndTurn,
    PayWithAssets,
    PlayActionCard,
    PlayProperty,
    PlayRent,
    RearrangeProperty,
    RespondJustSayNo,
)

VIEW_DETAILS = "__view_card_details__"
BACK = "__back__"


@dataclass(frozen=True, slots=True)
class CardGroupPick:
    """User chose a card that has more than one legal use."""

    card_id: str


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

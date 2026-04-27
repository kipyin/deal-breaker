"""Step-by-step pickers for long card-group submenus (rent, takeovers, etc.)."""

from __future__ import annotations

import questionary
from questionary import Choice
from questionary.prompts.common import InquirerControl, Separator

from dbreaker.cli.action_labels import card_display, format_action_label
from dbreaker.engine.actions import Action, PlayActionCard, PlayRent
from dbreaker.engine.cards import ActionSubtype, Card, PropertyColor

# Use nested wizards when a single card has more than this many legal uses.
NESTED_SUBMENU_THRESHOLD = 8


def can_use_shortcuts(choices: list[Choice]) -> bool:
    real = sum(1 for c in choices if not isinstance(c, Separator))
    return real <= len(InquirerControl.SHORTCUT_KEYS)


def hand_card_for_action_card(cards_index: dict[str, Card], card_id: str) -> Card | None:
    c = cards_index.get(card_id)
    if c is not None and c.action_subtype is not None:
        return c
    return None


def should_nested_play_action_wizard(
    group_actions: list[Action], cards_index: dict[str, Card]
) -> bool:
    if len(group_actions) <= NESTED_SUBMENU_THRESHOLD:
        return False
    if not all(isinstance(a, PlayActionCard) for a in group_actions):
        return False
    if not group_actions:
        return False
    first_id = group_actions[0].card_id
    if not all(isinstance(a, PlayActionCard) and a.card_id == first_id for a in group_actions):
        return False
    c = hand_card_for_action_card(cards_index, first_id)
    if c is None or c.action_subtype is None:
        return False
    return c.action_subtype in {
        ActionSubtype.FORCED_DEAL,
        ActionSubtype.SLY_DEAL,
        ActionSubtype.DEAL_BREAKER,
        ActionSubtype.DEBT_COLLECTOR,
    }


def should_nested_rent_wizard(group_actions: list[Action]) -> bool:
    if len(group_actions) <= NESTED_SUBMENU_THRESHOLD:
        return False
    if not all(isinstance(a, PlayRent) for a in group_actions):
        return False
    first_id = group_actions[0].card_id
    return all(isinstance(a, PlayRent) and a.card_id == first_id for a in group_actions)


def _back_choice() -> Choice:
    return Choice(title="Back", value="__back__")


def _pick_from_choices(
    title: str, choices: list[Choice]
) -> object | None:
    sel = questionary.select(
        title, choices=choices, use_shortcuts=can_use_shortcuts(choices)
    ).ask()
    return sel


def run_nested_rent_picker(
    player_id: str, group_actions: list[PlayRent], name_by_id: dict[str, str]
) -> Action | None:
    assert group_actions
    by_target: dict[str, list[PlayRent]] = {}
    for a in group_actions:
        by_target.setdefault(a.target_player_id, []).append(a)

    targets = sorted(by_target)
    t_choices: list[Choice] = [
        Choice(title=f"{i + 1}. {tid}", value=tid) for i, tid in enumerate(targets)
    ]
    t_choices.append(_back_choice())
    t_sel = _pick_from_choices(
        f"{player_id} — choose opponent for rent", t_choices
    )
    if t_sel in (None, "__back__"):
        return None
    assert isinstance(t_sel, str)
    rest = by_target[t_sel]
    if not rest:
        return None

    by_color: dict[PropertyColor | None, list[PlayRent]] = {}
    for a in rest:
        by_color.setdefault(a.color, []).append(a)

    colors = sorted(by_color, key=lambda c: c.value if c is not None else "")
    c_choices: list[Choice] = [
        Choice(
            title=f"{i + 1}. {c.value if c is not None else 'any / default'}",
            value=c,
        )
        for i, c in enumerate(colors)
    ]
    c_choices.append(_back_choice())
    c_sel = _pick_from_choices(
        f"{player_id} — choose rent color (card {group_actions[0].card_id})",
        c_choices,
    )
    if c_sel in (None, "__back__"):
        return None
    last = by_color.get(c_sel, [])
    if not last:
        return None
    with_double = [a for a in last if a.double_rent_card_id is not None]
    no_double = [a for a in last if a.double_rent_card_id is None]
    if len(no_double) == 1 and not with_double:
        return no_double[0]
    if len(with_double) == 1 and not no_double:
        return with_double[0]
    d_choices: list[Choice] = []
    for j, a in enumerate(sorted(no_double + with_double, key=lambda x: str(x))):
        label = format_action_label(a, name_by_id=name_by_id)
        d_choices.append(Choice(title=f"{j + 1}. {label}", value=a))
    d_choices.append(_back_choice())
    d_sel = _pick_from_choices(
        f"{player_id} — charge rent (or double rent)", d_choices
    )
    if d_sel in (None, "__back__") or not isinstance(d_sel, PlayRent):
        return None
    return d_sel


def run_nested_debt_collector_picker(
    player_id: str, group_actions: list[PlayActionCard], name_by_id: dict[str, str]
) -> Action | None:
    by_target: dict[str, list[PlayActionCard]] = {}
    for a in group_actions:
        if a.target_player_id is not None:
            by_target.setdefault(a.target_player_id, []).append(a)
    if not by_target:
        return None
    if len(by_target) == 1:
        return group_actions[0]
    t_choices = [
        Choice(title=f"{i + 1}. {tid}", value=tid) for i, tid in enumerate(sorted(by_target))
    ]
    t_choices.append(_back_choice())
    t_sel = _pick_from_choices(
        f"{player_id} — choose target (Debt Collector)", t_choices
    )
    if t_sel in (None, "__back__"):
        return None
    opts = by_target.get(str(t_sel), [])
    if len(opts) == 1:
        return opts[0]
    c2 = [
        Choice(
            title=f"{j + 1}. {format_action_label(o, name_by_id=name_by_id)}", value=o
        )
        for j, o in enumerate(opts)
    ]
    c2.append(_back_choice())
    a_sel = _pick_from_choices(f"{player_id} — confirm", c2)
    if a_sel in (None, "__back__") or not isinstance(a_sel, PlayActionCard):
        return None
    return a_sel


def run_nested_sly_deal_picker(
    player_id: str, group_actions: list[PlayActionCard], name_by_id: dict[str, str]
) -> Action | None:
    by_target: dict[str, list[PlayActionCard]] = {}
    for a in group_actions:
        if a.target_player_id is not None:
            by_target.setdefault(a.target_player_id, []).append(a)
    t_choices = [
        Choice(title=f"{i + 1}. {tid}", value=tid) for i, tid in enumerate(sorted(by_target))
    ]
    t_choices.append(_back_choice())
    t_sel = _pick_from_choices(
        f"{player_id} — Sly Deal: choose opponent", t_choices
    )
    if t_sel in (None, "__back__"):
        return None
    rest = [a for a in group_actions if a.target_player_id == t_sel and a.target_card_id]
    if not rest:
        return None
    by_card: dict[str, PlayActionCard] = {}
    for a in rest:
        if a.target_card_id and a.target_card_id not in by_card:
            by_card[a.target_card_id] = a
    c_choices: list[Choice] = [
        Choice(
            title=f"{i + 1}. {card_display(tc, name_by_id)}",
            value=by_card[tc],
        )
        for i, tc in enumerate(sorted(by_card, key=lambda x: (name_by_id.get(x, x), x)))
    ]
    c_choices.append(_back_choice())
    c_sel = _pick_from_choices(
        f"{player_id} — Sly Deal: take which property", c_choices
    )
    if c_sel in (None, "__back__") or not isinstance(c_sel, PlayActionCard):
        return None
    return c_sel


def run_nested_deal_breaker_picker(
    player_id: str, group_actions: list[PlayActionCard], name_by_id: dict[str, str]
) -> Action | None:
    by_target: dict[str, list[PlayActionCard]] = {}
    for a in group_actions:
        if a.target_player_id is not None:
            by_target.setdefault(a.target_player_id, []).append(a)
    t_choices = [
        Choice(title=f"{i + 1}. {tid}", value=tid) for i, tid in enumerate(sorted(by_target))
    ]
    t_choices.append(_back_choice())
    t_sel = _pick_from_choices(
        f"{player_id} — Deal Breaker: choose opponent", t_choices
    )
    if t_sel in (None, "__back__"):
        return None
    rest = [a for a in group_actions if a.target_player_id == t_sel and a.color is not None]
    if not rest:
        return None
    by_color: dict[PropertyColor, PlayActionCard] = {}
    for a in rest:
        if a.color and a.color not in by_color:
            by_color[a.color] = a
    c_choices: list[Choice] = []
    for i, col in enumerate(sorted(by_color, key=lambda c: c.value)):
        line = format_action_label(by_color[col], name_by_id=name_by_id)
        c_choices.append(
            Choice(title=f"{i + 1}. {col.value} — {line}", value=by_color[col])
        )
    c_choices.append(_back_choice())
    c_sel = _pick_from_choices(
        f"{player_id} — Deal Breaker: take which full set", c_choices
    )
    if c_sel in (None, "__back__") or not isinstance(c_sel, PlayActionCard):
        return None
    return c_sel


def run_nested_forced_deal_picker(
    player_id: str, group_actions: list[PlayActionCard], name_by_id: dict[str, str]
) -> Action | None:
    by_target: dict[str, list[PlayActionCard]] = {}
    for a in group_actions:
        if a.target_player_id is not None:
            by_target.setdefault(a.target_player_id, []).append(a)
    t_choices = [
        Choice(title=f"{i + 1}. {tid}", value=tid) for i, tid in enumerate(sorted(by_target))
    ]
    t_choices.append(_back_choice())
    t_sel = _pick_from_choices(
        f"{player_id} — Forced Deal: choose opponent", t_choices
    )
    if t_sel in (None, "__back__"):
        return None
    rest1 = [a for a in group_actions if a.target_player_id == t_sel]
    by_offer: dict[str, list[PlayActionCard]] = {}
    for a in rest1:
        if a.offered_card_id:
            by_offer.setdefault(a.offered_card_id, []).append(a)
    o_choices: list[Choice] = [
        Choice(
            title=f"{i + 1}. offer {card_display(oid, name_by_id)}",
            value=oid,
        )
        for i, oid in enumerate(sorted(by_offer, key=lambda x: (name_by_id.get(x, x), x)))
    ]
    o_choices.append(_back_choice())
    o_sel = _pick_from_choices(
        f"{player_id} — Forced Deal: offer which property", o_choices
    )
    if o_sel in (None, "__back__"):
        return None
    rest2 = by_offer.get(str(o_sel), [])
    by_req: dict[str, PlayActionCard] = {}
    for a in rest2:
        if a.requested_card_id and a.requested_card_id not in by_req:
            by_req[a.requested_card_id] = a
    r_choices: list[Choice] = [
        Choice(
            title=f"{i + 1}. take {card_display(rid, name_by_id)}",
            value=by_req[rid],
        )
        for i, rid in enumerate(sorted(by_req, key=lambda x: (name_by_id.get(x, x), x)))
    ]
    r_choices.append(_back_choice())
    r_sel = _pick_from_choices(
        f"{player_id} — Forced Deal: take which property from them", r_choices
    )
    if r_sel in (None, "__back__") or not isinstance(r_sel, PlayActionCard):
        return None
    return r_sel


def run_nested_play_action_picker(
    player_id: str,
    group_actions: list[Action],
    name_by_id: dict[str, str],
    cards_index: dict[str, Card],
) -> Action | None:
    if not all(isinstance(a, PlayActionCard) for a in group_actions):
        return None
    ac = [a for a in group_actions if isinstance(a, PlayActionCard)]
    if not ac:
        return None
    card_id = ac[0].card_id
    if not all(a.card_id == card_id for a in ac):
        return None
    c = hand_card_for_action_card(cards_index, card_id)
    if c is None or c.action_subtype is None:
        return None
    st = c.action_subtype
    if st == ActionSubtype.DEBT_COLLECTOR:
        return run_nested_debt_collector_picker(player_id, ac, name_by_id)
    if st == ActionSubtype.SLY_DEAL:
        return run_nested_sly_deal_picker(player_id, ac, name_by_id)
    if st == ActionSubtype.DEAL_BREAKER:
        return run_nested_deal_breaker_picker(player_id, ac, name_by_id)
    if st == ActionSubtype.FORCED_DEAL:
        return run_nested_forced_deal_picker(player_id, ac, name_by_id)
    return None

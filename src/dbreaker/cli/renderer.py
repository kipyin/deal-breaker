from __future__ import annotations

from collections.abc import Mapping, Sequence

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table

from dbreaker.cli.action_labels import format_action_label
from dbreaker.engine.actions import Action
from dbreaker.engine.cards import (
    RENT_LADDER_BY_COLOR,
    SET_SIZE_BY_COLOR,
    Card,
    CardKind,
    PropertyColor,
)
from dbreaker.engine.events import GameEvent
from dbreaker.engine.observation import Observation, OpponentObservation


def _completed_set_count(properties: Mapping[PropertyColor, Sequence[Card]]) -> int:
    completed = 0
    for color, cards in properties.items():
        needed = SET_SIZE_BY_COLOR.get(color)
        if needed is not None and len(cards) >= needed:
            completed += 1
    return completed


def build_card_name_map(observation: Observation) -> dict[str, str]:
    """Map card id -> display name for all cards visible in this observation."""
    names: dict[str, str] = {}

    def add(card: Card) -> None:
        names[card.id] = card.name

    for card in observation.hand:
        add(card)
    for card in observation.bank:
        add(card)
    for own_pile in observation.properties.values():
        for card in own_pile:
            add(card)
    for opponent in observation.opponents.values():
        for opp_pile in opponent.properties.values():
            for card in opp_pile:
                add(card)
    return names


def build_cards_index(observation: Observation) -> dict[str, Card]:
    """Map card id to ``Card`` for the human player's hand, bank, and property zones."""
    by_id: dict[str, Card] = {}
    for card in observation.hand:
        by_id[card.id] = card
    for card in observation.bank:
        by_id[card.id] = card
    for pile in observation.properties.values():
        for card in pile:
            by_id[card.id] = card
    return by_id


def _hand_line(observation: Observation) -> str:
    if not observation.hand:
        return "Hand: (empty)"
    parts = [f"{card.name} [{card.id}]" for card in observation.hand]
    return "Hand: " + ", ".join(parts)


def _bank_lines(observation: Observation) -> list[str]:
    if not observation.bank:
        return ["Bank: (empty)", "Bank value: 0"]
    parts = [f"{card.name} [{card.id}]" for card in observation.bank]
    total = sum(card.value for card in observation.bank)
    return [f"Bank: {', '.join(parts)}", f"Bank value: {total}"]


def _own_properties_lines(observation: Observation) -> list[str]:
    lines = ["Your properties:"]
    if not observation.properties:
        lines.append("  (none)")
        return lines
    for color in sorted(observation.properties.keys(), key=lambda c: c.value):
        cards = observation.properties[color]
        needed = SET_SIZE_BY_COLOR.get(color)
        count = len(cards)
        if needed is not None:
            complete = " complete" if count >= needed else ""
            status = f"{count}/{needed}{complete}"
        else:
            status = str(count)
        card_strs = [f"{c.name} [{c.id}]" for c in cards]
        lines.append(f"  {color.value}: {status} — {', '.join(card_strs)}")
    lines.append(f"Your completed sets: {_completed_set_count(observation.properties)}")
    return lines


def _opponent_lines(opponent: OpponentObservation) -> list[str]:
    lines = [
        f"--- {opponent.id} ({opponent.name}) ---",
        (
            f"  Hand size: {opponent.hand_size} | Bank value: {opponent.bank_value} "
            f"| Completed sets: {opponent.completed_sets}"
        ),
    ]
    if not opponent.properties:
        lines.append("  Properties: (none)")
        return lines
    lines.append("  Properties:")
    for color in sorted(opponent.properties.keys(), key=lambda c: c.value):
        cards = opponent.properties[color]
        needed = SET_SIZE_BY_COLOR.get(color)
        count = len(cards)
        if needed is not None:
            status = f"{count}/{needed}"
        else:
            status = str(count)
        card_strs = [f"{c.name} [{c.id}]" for c in cards]
        lines.append(f"    {color.value}: {status} — {', '.join(card_strs)}")
    return lines


def _observation_text_core(observation: Observation) -> list[str]:
    """Board lines without a legal-action list (shared by plain and Rich views)."""
    lines: list[str] = [
        (
            f"Turn {observation.turn} | Current: {observation.current_player_id} "
            f"| Active: {observation.active_player_id}"
        ),
        (
            f"Phase: {observation.phase.value} | Actions taken: {observation.actions_taken} "
            f"| Actions left: {observation.actions_left}"
        ),
    ]
    if observation.winner_id is not None:
        lines.append(f"Winner: {observation.winner_id}")
    if observation.pending_summary is not None:
        lines.append(f"Pending: {observation.pending_summary}")
    if observation.discard_required:
        lines.append(f"Discard required: {observation.discard_required}")
    lines.append(_hand_line(observation))
    lines.extend(_bank_lines(observation))
    lines.extend(_own_properties_lines(observation))
    lines.append("Opponents:")
    for opp_id in sorted(observation.opponents.keys()):
        lines.extend(_opponent_lines(observation.opponents[opp_id]))
    return lines


def render_observation(
    observation: Observation,
    legal_actions: list[Action] | None = None,
    *,
    include_legal_actions: bool = False,
) -> str:
    name_by_id = build_card_name_map(observation)
    lines = _observation_text_core(observation)
    if include_legal_actions and legal_actions is not None:
        lines.append("Legal actions:")
        lines.extend(
            f"  {index}. {format_action_label(action, name_by_id=name_by_id)}"
            for index, action in enumerate(legal_actions, start=1)
        )
    return "\n".join(lines)


def _hand_table(hand: list[Card]) -> Table:
    t = Table(title="Hand", box=box.ROUNDED, show_header=True, header_style="bold")
    t.add_column("Card", overflow="fold")
    t.add_column("ID", style="dim", overflow="fold")
    t.add_column("$", justify="right")
    for card in hand:
        t.add_row(card.name, card.id, str(card.value))
    if not hand:
        t.add_row("(empty)", "—", "0")
    return t


def _bank_table(bank: list[Card]) -> Table:
    t = Table(title="Bank", box=box.ROUNDED, show_header=True, header_style="bold")
    t.add_column("Card", overflow="fold")
    t.add_column("ID", style="dim", overflow="fold")
    t.add_column("$", justify="right")
    for card in bank:
        t.add_row(card.name, card.id, str(card.value))
    if not bank:
        t.add_row("(empty)", "—", "0")
    return t


def _properties_table(observation: Observation) -> Table:
    t = Table(title="Your properties", box=box.ROUNDED, show_header=True, header_style="bold")
    t.add_column("Color", style="bold")
    t.add_column("Progress", justify="right")
    t.add_column("Cards", overflow="fold")
    if not observation.properties:
        t.add_row("(none)", "—", "—")
        return t
    for color in sorted(observation.properties.keys(), key=lambda c: c.value):
        cards = observation.properties[color]
        needed = SET_SIZE_BY_COLOR.get(color)
        count = len(cards)
        if needed is not None:
            status = f"{count}/{needed}"
            if count >= needed:
                status += " (complete)"
        else:
            status = str(count)
        card_strs = ", ".join(f"{c.name} [{c.id}]" for c in cards)
        t.add_row(color.value, status, card_strs)
    t.add_row("Completed sets (total)", str(_completed_set_count(observation.properties)), "—")
    return t


def _opponent_table(opponent: OpponentObservation) -> Table:
    t = Table(
        title=f"{opponent.id} ({opponent.name})",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold",
    )
    t.add_column("Color", style="bold")
    t.add_column("Progress", justify="right")
    t.add_column("Cards", overflow="fold")
    if not opponent.properties:
        t.add_row(
            "—",
            f"Hand {opponent.hand_size} | Bank ${opponent.bank_value}",
            "(no properties)",
        )
    else:
        info = (
            f"Hand {opponent.hand_size} | Bank ${opponent.bank_value} | "
            f"Sets {opponent.completed_sets}"
        )
        t.add_row("Info", "", info)
        for color in sorted(opponent.properties.keys(), key=lambda c: c.value):
            cards = opponent.properties[color]
            needed = SET_SIZE_BY_COLOR.get(color)
            count = len(cards)
            status = f"{count}/{needed}" if needed is not None else str(count)
            card_strs = ", ".join(f"{c.name} [{c.id}]" for c in cards)
            t.add_row(color.value, status, card_strs)
    return t


def render_status_panel(observation: Observation) -> Panel:
    text = "\n".join(
        [
            f"Turn {observation.turn}  ·  Current: {observation.current_player_id}  ·  "
            f"Active: {observation.active_player_id}",
            f"Phase: {observation.phase.value}  ·  Actions taken: "
            f"{observation.actions_taken}  ·  Actions left: {observation.actions_left}",
        ]
    )
    if observation.winner_id is not None:
        text += f"\nWinner: {observation.winner_id}"
    if observation.pending_summary is not None:
        text += f"\nPending: {observation.pending_summary}"
    if observation.discard_required:
        text += f"\nDiscard required: {observation.discard_required}"
    return Panel(text, title="Status", box=box.ROUNDED)


def render_observation_rich(observation: Observation) -> RenderableType:
    """Colored, tabular view of the board (no legal-action dump)."""
    pieces: list[RenderableType] = [render_status_panel(observation)]
    pieces.append(_hand_table(observation.hand))
    pieces.append(_bank_table(observation.bank))
    pieces.append(_properties_table(observation))
    for opp_id in sorted(observation.opponents.keys()):
        pieces.append(_opponent_table(observation.opponents[opp_id]))
    return Group(*pieces)


def card_details_rich(card: Card) -> RenderableType:
    """Rich table with rules-relevant context for a single card."""
    t = Table(title=card.name, box=box.ROUNDED, show_header=True, header_style="bold")
    t.add_column("Field", style="dim", overflow="fold")
    t.add_column("Value", overflow="fold")
    t.add_row("id", card.id)
    t.add_row("Kind", str(card.kind))
    t.add_row("Bank value", str(card.value))
    if card.kind == CardKind.PROPERTY and card.color is not None:
        t.add_row("Color", str(card.color.value))
        need = SET_SIZE_BY_COLOR.get(card.color)
        if need is not None:
            t.add_row("To complete a set", f"{need} of this color")
        ladder = RENT_LADDER_BY_COLOR.get(card.color)
        if ladder is not None and card.color in (PropertyColor.RAILROAD, PropertyColor.UTILITY):
            t.add_row("Rent steps (size of set)", " → ".join(f"${x}M" for x in ladder))
        elif ladder is not None:
            t.add_row("Rent ladder (size of this-color set)", " → ".join(f"${x}M" for x in ladder))
    if card.kind == CardKind.WILD_PROPERTY and card.colors:
        if len(card.colors) >= 9:
            t.add_row("Plays as", "Any color (choose when you play the card)")
        else:
            t.add_row("May play as", ", ".join(c.value for c in card.colors))
    if card.kind == CardKind.RENT and card.colors:
        if PropertyColor.ANY in card.colors:
            t.add_row("Applies to", "Any one color set you have on the table")
        else:
            t.add_row(
                "Applies to",
                ", ".join(c.value for c in card.colors) + " (matching sets of yours on the table)",
            )
    if card.action_subtype is not None:
        t.add_row("Action", str(card.action_subtype.value).replace("_", " "))
    return t


def render_events(events: list[GameEvent]) -> str:
    return "\n".join(event.reason_summary or event.type for event in events)


def format_ai_turn_header(player_id: str, action: Action, *, name_by_id: dict[str, str]) -> str:
    return f"[AI {player_id}] {format_action_label(action, name_by_id=name_by_id)}"

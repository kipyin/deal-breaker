from __future__ import annotations

from collections.abc import Mapping, Sequence

from dbreaker.cli.action_labels import format_action_label
from dbreaker.engine.actions import Action
from dbreaker.engine.cards import SET_SIZE_BY_COLOR, Card, PropertyColor
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


def render_observation(observation: Observation, legal_actions: list[Action]) -> str:
    name_by_id = build_card_name_map(observation)
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
    lines.append("Legal actions:")
    lines.extend(
        f"  {index}. {format_action_label(action, name_by_id=name_by_id)}"
        for index, action in enumerate(legal_actions, start=1)
    )
    return "\n".join(lines)


def render_events(events: list[GameEvent]) -> str:
    return "\n".join(event.reason_summary or event.type for event in events)


def format_ai_turn_header(player_id: str, action: Action, *, name_by_id: dict[str, str]) -> str:
    return f"[AI {player_id}] {format_action_label(action, name_by_id=name_by_id)}"

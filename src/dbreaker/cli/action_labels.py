from __future__ import annotations

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


def card_display(card_id: str, name_by_id: dict[str, str]) -> str:
    """Prefer ``name [id]`` when the card appears in the observation map, else ``id``."""
    name = name_by_id.get(card_id)
    if name is not None:
        return f"{name} [{card_id}]"
    return card_id


def format_action_label(action: Action, *, name_by_id: dict[str, str] | None = None) -> str:
    """Human-readable label for menus, board view, and AI summaries."""
    names = name_by_id or {}
    if isinstance(action, DrawCards):
        return "Draw cards"
    if isinstance(action, BankCard):
        return f"Bank {card_display(action.card_id, names)}"
    if isinstance(action, PlayProperty):
        return f"Play {card_display(action.card_id, names)} as {action.color.value}"
    if isinstance(action, PlayRent):
        title = f"Charge {action.target_player_id} rent with {card_display(action.card_id, names)}"
        if action.color is not None:
            title += f" for {action.color.value}"
        if action.double_rent_card_id is not None:
            title += f" and double with {card_display(action.double_rent_card_id, names)}"
        return title
    if isinstance(action, PlayActionCard):
        parts = [f"Play {card_display(action.card_id, names)}"]
        if action.target_player_id is not None:
            parts.append(f"target {action.target_player_id}")
        if action.target_card_id is not None:
            parts.append(f"take {card_display(action.target_card_id, names)}")
        if action.offered_card_id is not None or action.requested_card_id is not None:
            if action.offered_card_id is not None:
                parts.append(f"offer {card_display(action.offered_card_id, names)}")
            if action.requested_card_id is not None:
                parts.append(f"request {card_display(action.requested_card_id, names)}")
        if action.color is not None:
            parts.append(f"color {action.color.value}")
        return " ".join(parts)
    if isinstance(action, PayWithAssets):
        if not action.card_ids:
            return "Pay with nothing"
        return "Pay with " + ", ".join(card_display(cid, names) for cid in action.card_ids)
    if isinstance(action, DiscardCard):
        return f"Discard {card_display(action.card_id, names)}"
    if isinstance(action, RearrangeProperty):
        return f"Move {card_display(action.card_id, names)} to {action.color.value}"
    if isinstance(action, EndTurn):
        return "End turn"
    if isinstance(action, RespondJustSayNo):
        if action.accept:
            return "Accept pending effect"
        if action.card_id is not None:
            return f"Just Say No with {card_display(action.card_id, names)}"
        return "Just Say No"
    return str(action)

from __future__ import annotations

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
from dbreaker.engine.cards import PropertyColor


def parse_command(command: str) -> Action:
    parts = command.strip().split()
    if not parts:
        raise ValueError("empty command")
    verb = parts[0].lower()
    if verb == "end":
        return EndTurn()
    if verb == "bank" and len(parts) == 2:
        return BankCard(card_id=parts[1])
    if verb == "discard" and len(parts) == 2:
        return DiscardCard(card_id=parts[1])
    if verb == "pay":
        return PayWithAssets(card_ids=tuple(parts[1:]))
    if verb == "accept":
        return RespondJustSayNo(card_id=None, accept=True)
    if verb == "no" and len(parts) == 2:
        return RespondJustSayNo(card_id=parts[1], accept=False)
    if verb == "property" and len(parts) == 3:
        return PlayProperty(card_id=parts[1], color=PropertyColor(parts[2]))
    if verb == "rearrange" and len(parts) == 3:
        return RearrangeProperty(card_id=parts[1], color=PropertyColor(parts[2]))
    if verb == "pass-go" and len(parts) == 2:
        return PlayActionCard(card_id=parts[1])
    if verb == "debt" and len(parts) == 4 and parts[2] == "target":
        return PlayActionCard(card_id=parts[1], target_player_id=parts[3])
    if verb in {"house", "hotel"} and len(parts) == 3:
        return PlayActionCard(card_id=parts[1], color=PropertyColor(parts[2]))
    if verb == "deal-breaker" and len(parts) == 5 and parts[2] == "target":
        return PlayActionCard(
            card_id=parts[1],
            target_player_id=parts[3],
            color=PropertyColor(parts[4]),
        )
    if verb == "sly" and len(parts) == 5 and parts[2] == "target":
        return PlayActionCard(
            card_id=parts[1],
            target_player_id=parts[3],
            target_card_id=parts[4],
        )
    if verb == "forced" and len(parts) == 7 and parts[2] == "target":
        return PlayActionCard(
            card_id=parts[1],
            target_player_id=parts[3],
            offered_card_id=parts[4],
            requested_card_id=parts[6],
        )
    if verb == "play" and len(parts) >= 4 and "target" in parts:
        target_index = parts.index("target")
        if target_index + 1 >= len(parts):
            raise ValueError("target requires player id")
        color = _option_value(parts, "color")
        double = _option_value(parts, "double")
        return PlayRent(
            card_id=parts[1],
            target_player_id=parts[target_index + 1],
            color=PropertyColor(color) if color is not None else None,
            double_rent_card_id=double,
        )
    raise ValueError(f"unsupported command: {command}")


def _option_value(parts: list[str], option: str) -> str | None:
    if option not in parts:
        return None
    index = parts.index(option)
    if index + 1 >= len(parts):
        raise ValueError(f"{option} requires a value")
    return parts[index + 1]


def format_shortcut_help() -> str:
    """Human-readable examples for ``parse_command`` shortcuts (play in terminal)."""
    lines = [
        "Shortcut commands — use card IDs shown as [id] on the board:",
        "  end",
        "    End turn.",
        "  bank <card_id>",
        "    Bank a card from your hand.",
        "  discard <card_id>",
        "    Discard a card from your hand.",
        "  pay [<card_id> ...]",
        "    Pay pending debt with those assets (or 'pay' alone for empty payment if legal).",
        "  accept",
        "    Accept the pending effect (no Just Say No).",
        "  no <just_say_no_card_id>",
        "    Block with Just Say No.",
        "  property <card_id> <color>",
        "    Play a property/wild as color (e.g. blue, railroad).",
        "  rearrange <card_id> <color>",
        "    Move a property card to another color pile.",
        "  pass-go <card_id>",
        "  debt <card_id> target <player_id>",
        "  house <card_id> <color>",
        "  hotel <card_id> <color>",
        "  deal-breaker <card_id> target <player_id> <color>",
        "  sly <card_id> target <player_id> <target_card_id>",
        "  forced <card_id> target <player_id> <offer_card_id> for <request_card_id>",
        "  play <rent_card_id> target <player_id> [color <color>] [double <double_rent_card_id>]",
        "    Example: play rent-blue-1 target P2 color blue double double-the-rent-1",
    ]
    return "\n".join(lines)

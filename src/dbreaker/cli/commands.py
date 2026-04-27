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
from dbreaker.engine.cards import PropertyColor


def matching_legal_action(action: Action, legal_actions: list[Action]) -> Action | None:
    """Map a parsed command to a matching entry in ``legal_actions``.

    ``PayWithAssets`` matches by sorted card id tuple.
    """
    if action in legal_actions:
        return action
    if isinstance(action, PayWithAssets):
        requested = sorted(action.card_ids)
        for legal in legal_actions:
            if (
                isinstance(legal, PayWithAssets)
                and sorted(legal.card_ids) == requested
            ):
                return legal
    return None


def legal_action_for_command(command_text: str, legal_actions: list[Action]) -> Action:
    """Parse ``command_text`` and return the matching legal action.

    Raises ``ValueError`` if the parse failed or the action is not legal.
    """
    try:
        action = parse_command(command_text)
    except ValueError as exc:
        raise ValueError(f"parse error: {exc}") from exc
    matched = matching_legal_action(action, legal_actions)
    if matched is None:
        raise ValueError("command is not legal in the current state")
    return matched


def parse_command(command: str) -> Action:
    parts = command.strip().split()
    if not parts:
        raise ValueError("empty command")
    verb = parts[0].lower()
    if verb == "draw":
        return DrawCards()
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
    """Full shortcut reference: same as ``format_shortcut_help_all``."""
    return format_shortcut_help_all()


def format_shortcut_help_all() -> str:
    """Human-readable examples for all ``parse_command`` shortcuts."""
    lines = [
        "Shortcut commands — use card IDs shown as [id] on the board:",
        "  draw",
        "    Draw when you are in the draw phase.",
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


def format_shortcut_help_topic(topic: str) -> str:
    """Topic-based shortcut help (use keys from ``short_help_topic_choices``)."""
    t = topic.lower()
    if t in {"basic", "turn"}:
        return "\n".join(
            [
                "Basic / turn",
                "  draw — in draw phase",
                "  end — end turn",
                "  bank <card_id> — from hand to bank",
                "  discard <card_id> — hand discard when required",
            ]
        )
    if t in {"pay", "payment"}:
        return "\n".join(
            [
                "Paying debt (assets are bank and built properties, not hand)",
                "  pay [<card_id> ...] — use those card IDs, or 'pay' alone for empty if legal",
            ]
        )
    if t in {"property", "prop"}:
        return "\n".join(
            [
                "Property on the table",
                "  property <card_id> <color> — play from hand to table",
                "  rearrange <card_id> <color> — move between color piles",
            ]
        )
    if t in {"action", "action_cards", "actions"}:
        return "\n".join(
            [
                "Action cards (examples; full list: choose “All commands” in help menu)",
                "  pass-go <card_id>",
                "  debt <card_id> target <player_id>",
                "  house <card_id> <color>   hotel <card_id> <color>",
                "  deal-breaker <card_id> target <player_id> <color>",
                "  sly <card_id> target <player_id> <target_card_id>",
                "  forced <card_id> target <player_id> <offer_card_id> for <request_card_id>",
            ]
        )
    if t in {"rent", "rents"}:
        return "\n".join(
            [
                "Rent",
                (
                    "  play <rent_card_id> target <player_id> "
                    "[color <color>] [double <double_rent_card_id>]"
                ),
                (
                    "  Example: play rent-blue-1 target P2 color blue "
                    "double double-the-rent-1"
                ),
            ]
        )
    if t in {"respond", "jsn"}:
        return "\n".join(
            [
                "Responding to an effect",
                "  accept — take the effect (no block)",
                "  no <just_say_no_card_id> — block with Just Say No if legal",
            ]
        )
    if t in {"all", "full", "*"}:
        return format_shortcut_help_all()
    return f"Unknown help topic: {topic!r}. Use topic keys: {shortcut_help_topic_keys()}"


def shortcut_help_topic_keys() -> list[str]:
    return [
        "basic",
        "pay",
        "property",
        "action",
        "rent",
        "respond",
        "all",
    ]


def short_help_topic_choices() -> list[tuple[str, str]]:
    """(value_key, display_title) for questionary help submenu."""
    return [
        ("basic", "Basic / turn (draw, end, bank, discard)"),
        ("pay", "Paying debt"),
        ("property", "Property & rearrange"),
        ("action", "Action cards (Pass Go, Debt, Sly, …)"),
        ("rent", "Charge rent (play command)"),
        ("respond", "Just Say No / accept"),
        ("all", "All commands (full reference)"),
    ]

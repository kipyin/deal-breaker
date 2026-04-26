from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dbreaker.engine.cards import PropertyColor


class Action:
    """Marker base class for player intent actions."""


@dataclass(frozen=True, slots=True)
class DrawCards(Action):
    pass


@dataclass(frozen=True, slots=True)
class BankCard(Action):
    card_id: str


@dataclass(frozen=True, slots=True)
class PlayProperty(Action):
    card_id: str
    color: PropertyColor


@dataclass(frozen=True, slots=True)
class PlayRent(Action):
    card_id: str
    target_player_id: str
    color: PropertyColor | None = None
    double_rent_card_id: str | None = None


@dataclass(frozen=True, slots=True)
class PlayActionCard(Action):
    card_id: str
    target_player_id: str | None = None
    target_card_id: str | None = None
    offered_card_id: str | None = None
    requested_card_id: str | None = None
    color: PropertyColor | None = None


@dataclass(frozen=True, slots=True)
class PayWithAssets(Action):
    card_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DiscardCard(Action):
    card_id: str


@dataclass(frozen=True, slots=True)
class RearrangeProperty(Action):
    card_id: str
    color: PropertyColor


@dataclass(frozen=True, slots=True)
class EndTurn(Action):
    pass


@dataclass(frozen=True, slots=True)
class RespondJustSayNo(Action):
    card_id: str | None
    accept: bool


def action_to_payload(action: Action) -> dict[str, Any]:
    if isinstance(action, DrawCards):
        return {"type": "DrawCards"}
    if isinstance(action, BankCard):
        return {"type": "BankCard", "card_id": action.card_id}
    if isinstance(action, PlayProperty):
        return {
            "type": "PlayProperty",
            "card_id": action.card_id,
            "color": action.color.value,
        }
    if isinstance(action, PlayRent):
        return {
            "type": "PlayRent",
            "card_id": action.card_id,
            "target_player_id": action.target_player_id,
            "color": action.color.value if action.color is not None else None,
            "double_rent_card_id": action.double_rent_card_id,
        }
    if isinstance(action, PlayActionCard):
        return {
            "type": "PlayActionCard",
            "card_id": action.card_id,
            "target_player_id": action.target_player_id,
            "target_card_id": action.target_card_id,
            "offered_card_id": action.offered_card_id,
            "requested_card_id": action.requested_card_id,
            "color": action.color.value if action.color is not None else None,
        }
    if isinstance(action, PayWithAssets):
        return {"type": "PayWithAssets", "card_ids": list(action.card_ids)}
    if isinstance(action, DiscardCard):
        return {"type": "DiscardCard", "card_id": action.card_id}
    if isinstance(action, RearrangeProperty):
        return {
            "type": "RearrangeProperty",
            "card_id": action.card_id,
            "color": action.color.value,
        }
    if isinstance(action, EndTurn):
        return {"type": "EndTurn"}
    if isinstance(action, RespondJustSayNo):
        return {
            "type": "RespondJustSayNo",
            "card_id": action.card_id,
            "accept": action.accept,
        }
    raise ValueError(f"unsupported action type: {type(action).__name__}")


def action_from_payload(payload: dict[str, Any]) -> Action:
    action_type = payload["type"]
    if action_type == "DrawCards":
        return DrawCards()
    if action_type == "BankCard":
        return BankCard(card_id=payload["card_id"])
    if action_type == "PlayProperty":
        return PlayProperty(
            card_id=payload["card_id"],
            color=PropertyColor(payload["color"]),
        )
    if action_type == "PlayRent":
        color = payload.get("color")
        return PlayRent(
            card_id=payload["card_id"],
            target_player_id=payload["target_player_id"],
            color=PropertyColor(color) if color is not None else None,
            double_rent_card_id=payload.get("double_rent_card_id"),
        )
    if action_type == "PlayActionCard":
        color = payload.get("color")
        return PlayActionCard(
            card_id=payload["card_id"],
            target_player_id=payload.get("target_player_id"),
            target_card_id=payload.get("target_card_id"),
            offered_card_id=payload.get("offered_card_id"),
            requested_card_id=payload.get("requested_card_id"),
            color=PropertyColor(color) if color is not None else None,
        )
    if action_type == "PayWithAssets":
        return PayWithAssets(card_ids=tuple(payload["card_ids"]))
    if action_type == "DiscardCard":
        return DiscardCard(card_id=payload["card_id"])
    if action_type == "RearrangeProperty":
        return RearrangeProperty(
            card_id=payload["card_id"],
            color=PropertyColor(payload["color"]),
        )
    if action_type == "EndTurn":
        return EndTurn()
    if action_type == "RespondJustSayNo":
        return RespondJustSayNo(
            card_id=payload.get("card_id"),
            accept=payload["accept"],
        )
    raise ValueError(f"unsupported action payload type: {action_type}")

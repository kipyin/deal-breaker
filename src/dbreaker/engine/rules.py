from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class GamePhase(StrEnum):
    DRAW = "draw"
    ACTION = "action"
    DISCARD = "discard"
    RESPOND = "respond"
    PAYMENT = "payment"
    GAME_OVER = "game_over"


class RentWildPropertyMode(StrEnum):
    OFFICIAL = "official"
    NEVER = "never"
    ALWAYS = "always"


class PropertyRearrangeTiming(StrEnum):
    BEFORE_ACTION = "before_action"
    ANYTIME_ON_TURN = "anytime_on_turn"
    NEVER = "never"


@dataclass(frozen=True, slots=True)
class RuleConfig:
    allow_just_say_no_chain: bool = True
    rent_with_wild_property: RentWildPropertyMode = RentWildPropertyMode.OFFICIAL
    property_rearrange_timing: PropertyRearrangeTiming = PropertyRearrangeTiming.BEFORE_ACTION
    starting_hand_size: int = 5
    draw_count: int = 2
    empty_hand_draw_count: int = 5
    hand_limit: int = 7
    actions_per_turn: int = 3
    sets_to_win: int = 3
    # When True, an empty draw pile is refilled by shuffling the discard pile (official rule).
    reshuffle_discard_when_deck_empty: bool = True

    @classmethod
    def official(cls) -> RuleConfig:
        return cls()

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> RuleConfig:
        defaults = cls.official()
        return cls(
            allow_just_say_no_chain=bool(
                mapping.get("allow_just_say_no_chain", defaults.allow_just_say_no_chain)
            ),
            rent_with_wild_property=RentWildPropertyMode(
                mapping.get("rent_with_wild_property", defaults.rent_with_wild_property)
            ),
            property_rearrange_timing=PropertyRearrangeTiming(
                mapping.get("property_rearrange_timing", defaults.property_rearrange_timing)
            ),
            starting_hand_size=int(mapping.get("starting_hand_size", defaults.starting_hand_size)),
            draw_count=int(mapping.get("draw_count", defaults.draw_count)),
            empty_hand_draw_count=int(
                mapping.get("empty_hand_draw_count", defaults.empty_hand_draw_count)
            ),
            hand_limit=int(mapping.get("hand_limit", defaults.hand_limit)),
            actions_per_turn=int(mapping.get("actions_per_turn", defaults.actions_per_turn)),
            sets_to_win=int(mapping.get("sets_to_win", defaults.sets_to_win)),
            reshuffle_discard_when_deck_empty=bool(
                mapping.get(
                    "reshuffle_discard_when_deck_empty",
                    defaults.reshuffle_discard_when_deck_empty,
                )
            ),
        )

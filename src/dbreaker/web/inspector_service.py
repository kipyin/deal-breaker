from __future__ import annotations

from dataclasses import asdict
from typing import Any

from dbreaker.cli.action_labels import format_action_label
from dbreaker.cli.renderer import build_card_name_map
from dbreaker.engine.actions import Action, action_to_payload
from dbreaker.engine.game import Game
from dbreaker.engine.observation import Observation, OpponentObservation, PendingObservation
from dbreaker.web.serialization import card_to_json, property_table_json, property_table_opp

_GAME_END_PHASE = "ended"


def _pending_json(p: PendingObservation | None) -> dict[str, Any] | None:
    if p is None:
        return None
    return {
        "kind": p.kind,
        "actor_id": p.actor_id,
        "target_id": p.target_id,
        "respond_player_id": p.respond_player_id,
        "amount": p.amount,
        "source_card_name": p.source_card_name,
        "reason": p.reason,
        "negated": p.negated,
    }


def _opponent_row(o: OpponentObservation) -> dict[str, Any]:
    return {
        "id": o.id,
        "name": o.name,
        "hand_size": o.hand_size,
        "bank": [card_to_json(card) for card in o.bank],
        "bank_value": o.bank_value,
        "properties": property_table_opp(o.properties),
        "completed_sets": o.completed_sets,
    }


def _phase_value(game: Game) -> str:
    if game.state.winner_id is not None:
        return _GAME_END_PHASE
    return game.state.phase.value


def _viewer_json(obs: Observation) -> dict[str, Any]:
    return {
        "player_id": obs.player_id,
        "hand": [card_to_json(c) for c in obs.hand],
        "bank": [card_to_json(c) for c in obs.bank],
        "properties": property_table_json(obs.properties),
        "actions_taken": obs.actions_taken,
        "actions_left": obs.actions_left,
        "discard_required": obs.discard_required,
    }


def _serialize_legal_action(
    index: int, action: Action, name_by_id: dict[str, str]
) -> dict[str, Any]:
    return {
        "id": f"a_{index:04d}",
        "label": format_action_label(action, name_by_id=name_by_id),
        "payload": action_to_payload(action),
    }


def build_inspector_state(
    game: Game,
    *,
    game_id: str,
    viewer: str,
    omniscient: bool = False,
) -> dict[str, Any]:
    """Return JSON-serializable inspector state for a live or replayed game."""
    version = len(game.action_log)
    obs = game.observation_for(viewer, omniscient=omniscient)
    name_by_id = build_card_name_map(obs)
    current = game.active_player_id
    # Legal actions must be for the *viewer* (the seat the UI posts as), not
    # always the active player. The active player can differ (e.g. response phase).
    legal = game.legal_actions(viewer) if not game.is_terminal() else []
    legal_actions = [
        _serialize_legal_action(i, a, name_by_id) for i, a in enumerate(legal)
    ]
    timeline: list[dict[str, Any]] = []
    for i, event in enumerate(game.event_log):
        d = asdict(event)
        d["index"] = i
        timeline.append(d)
    last_action: dict[str, Any] | None = None
    if game.action_log:
        last = game.action_log[-1]
        last_action = {
            "player_id": last["player_id"],
            "payload": last["action_payload"],
        }
    gs = game.state
    deck_count = len(gs.deck)
    discard_count = len(gs.discard)
    discard_top = card_to_json(gs.discard[-1]) if gs.discard else None
    return {
        "game_id": game_id,
        "version": version,
        "status": "active" if not game.is_terminal() else "completed",
        "turn": game.state.turn,
        "phase": _phase_value(game),
        "current_player_id": game.state.current_player_id,
        "active_player_id": current,
        "winner_id": game.state.winner_id,
        "viewer": _viewer_json(obs),
        "opponents": [_opponent_row(o) for o in obs.opponents.values()],
        "pending": _pending_json(obs.pending),
        "legal_actions": legal_actions,
        "timeline": timeline,
        "last_action": last_action,
        "deck_count": deck_count,
        "discard_count": discard_count,
        "discard_top": discard_top,
    }

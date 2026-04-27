"""Inspector legal actions must be scoped to the requested viewer, not the active player."""

from __future__ import annotations

from dbreaker.engine.cards import ActionSubtype, Card, CardKind
from dbreaker.engine.game import Game
from dbreaker.engine.rules import GamePhase
from dbreaker.engine.state import PendingEffect
from dbreaker.web.inspector_service import build_inspector_state


def _action(card_id: str, subtype: ActionSubtype) -> Card:
    return Card(
        id=card_id,
        name=card_id,
        kind=CardKind.ACTION,
        value=3,
        action_subtype=subtype,
    )


def test_inspector_legal_actions_respond_phase_use_viewer_not_active_player() -> None:
    # P1 is "current" on the turn clock; P2 must respond to a pending effect.
    # Human web UI fetches as P1 (viewer) but only P2 may post response actions.
    debt = _action("debt", ActionSubtype.DEBT_COLLECTOR)
    jsn = _action("jsn-1", ActionSubtype.JUST_SAY_NO)
    game = Game.new(player_count=2, seed=1, preset_hands=[[debt], [jsn]])
    game.state.phase = GamePhase.RESPOND
    assert game.state.current_player_id == "P1"
    game.state.pending_effect = PendingEffect(
        kind="payment",
        actor_id="P1",
        target_id="P2",
        source_card=debt,
        respond_player_id="P2",
        amount=5,
    )
    assert game.active_player_id == "P2"

    p1_ins = build_inspector_state(game, game_id="g1", viewer="P1")
    assert p1_ins["active_player_id"] == "P2"
    assert p1_ins["current_player_id"] == "P1"
    assert not any(
        a["payload"].get("type") == "RespondJustSayNo"
        for a in p1_ins.get("legal_actions", [])
    )

    p2_ins = build_inspector_state(game, game_id="g1", viewer="P2")
    assert any(
        a["payload"].get("type") == "RespondJustSayNo"
        for a in p2_ins.get("legal_actions", [])
    )

from dbreaker.cli.renderer import render_observation
from dbreaker.engine.actions import PayWithAssets, RespondJustSayNo
from dbreaker.engine.cards import ActionSubtype, Card, CardKind
from dbreaker.engine.game import Game
from dbreaker.engine.player import PlayerState
from dbreaker.engine.rules import GamePhase
from dbreaker.engine.state import PendingEffect
from dbreaker.strategies.heuristic import BasicHeuristicStrategy


def action(card_id: str, subtype: ActionSubtype, value: int = 3) -> Card:
    return Card(
        id=card_id,
        name=card_id,
        kind=CardKind.ACTION,
        value=value,
        action_subtype=subtype,
    )


def money(card_id: str, value: int) -> Card:
    return Card(id=card_id, name=card_id, kind=CardKind.MONEY, value=value)


def test_game_active_player_follows_pending_response_and_observation_exposes_details() -> None:
    debt = action("debt", ActionSubtype.DEBT_COLLECTOR)
    game = Game.new(player_count=2, seed=1, preset_hands=[[debt], []])
    game.state.phase = GamePhase.RESPOND
    game.state.pending_effect = PendingEffect(
        kind="payment",
        actor_id="P1",
        target_id="P2",
        source_card=debt,
        respond_player_id="P2",
        amount=5,
    )

    observation = game.observation_for("P2")

    assert game.active_player_id == "P2"
    assert observation.active_player_id == "P2"
    assert observation.pending is not None
    assert observation.pending.kind == "payment"
    assert observation.pending.actor_id == "P1"
    assert observation.pending.target_id == "P2"
    assert observation.pending.amount == 5
    assert observation.pending.respond_player_id == "P2"
    assert observation.pending.source_card_name == "debt"


def test_renderer_shows_phase_actions_pending_and_discard_pressure() -> None:
    game = Game.new(
        player_count=2,
        seed=1,
        preset_hands=[[money(f"m{i}", 1) for i in range(8)], []],
    )
    game.state.phase = GamePhase.DISCARD

    rendered = render_observation(game.observation_for("P1"), game.legal_actions("P1"))

    assert "Phase: discard" in rendered
    assert "Actions left:" in rendered
    assert "Discard required: 1" in rendered
    assert "[m0]" in rendered
    assert "Opponents:" in rendered
    assert "Legal actions:" in rendered
    assert "PlayRent(" not in rendered


def test_basic_strategy_handles_payment_and_response_pending_actions() -> None:
    game = Game.new(player_count=2, seed=1, preset_hands=[[], []])
    game.state.players["P1"] = PlayerState(
        id="P1",
        name="P1",
        bank=[money("m5", 5), money("m1", 1)],
    )
    game.state.set_pending_payment(payer_id="P1", receiver_id="P2", amount=4, reason="rent")

    payment_actions = game.legal_actions("P1")
    payment_decision = BasicHeuristicStrategy().choose_action(
        game.observation_for("P1"), payment_actions
    )

    assert payment_decision.action == PayWithAssets(card_ids=("m5",))

    game.state.pending_payment = None
    game.state.pending_effect = PendingEffect(
        kind="payment",
        actor_id="P2",
        target_id="P1",
        source_card=action("debt", ActionSubtype.DEBT_COLLECTOR),
        respond_player_id="P1",
        amount=5,
    )
    game.state.phase = GamePhase.RESPOND

    response_actions = game.legal_actions("P1")
    response_decision = BasicHeuristicStrategy().choose_action(
        game.observation_for("P1"), response_actions
    )

    assert response_decision.action == RespondJustSayNo(card_id=None, accept=True)

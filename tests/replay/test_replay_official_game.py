from dbreaker.engine.actions import (
    DrawCards,
    PayWithAssets,
    PlayActionCard,
    PlayProperty,
    PlayRent,
    RespondJustSayNo,
)
from dbreaker.engine.cards import ActionSubtype, Card, CardKind, PropertyColor
from dbreaker.engine.game import Game
from dbreaker.engine.rules import GamePhase
from dbreaker.replay import player as replay_player


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


def prop(card_id: str, value: int, color: PropertyColor) -> Card:
    return Card(
        id=card_id,
        name=card_id,
        kind=CardKind.PROPERTY,
        value=value,
        color=color,
    )


def rent(card_id: str, colors: tuple[PropertyColor, ...]) -> Card:
    return Card(id=card_id, name=card_id, kind=CardKind.RENT, value=1, colors=colors)


def test_records_from_game_capture_action_payloads_and_event_digests() -> None:
    assert hasattr(replay_player, "records_from_game")
    debt = action("debt", ActionSubtype.DEBT_COLLECTOR)
    game = Game.new(player_count=2, seed=4, preset_hands=[[debt], []])
    game.state.phase = GamePhase.ACTION

    game.step("P1", PlayActionCard(card_id="debt", target_player_id="P2"))
    game.step("P2", RespondJustSayNo(card_id=None, accept=True))

    records = replay_player.records_from_game(game)

    assert [record.player_id for record in records] == ["P1", "P2"]
    assert records[0].action_payload == {
        "type": "PlayActionCard",
        "card_id": "debt",
        "target_player_id": "P2",
        "target_card_id": None,
        "offered_card_id": None,
        "requested_card_id": None,
        "color": None,
    }
    assert records[0].before_digest != records[0].after_digest
    assert records[0].event_digests == tuple(event.digest() for event in game.event_log[:1])


def test_replay_records_verifies_deterministic_action_stream() -> None:
    debt = action("debt", ActionSubtype.DEBT_COLLECTOR)
    source = Game.new(player_count=2, seed=4, preset_hands=[[debt], []])
    source.state.phase = GamePhase.ACTION
    source.step("P1", PlayActionCard(card_id="debt", target_player_id="P2"))
    source.step("P2", RespondJustSayNo(card_id=None, accept=True))

    replayed = replay_player.replay_records(
        player_count=2,
        seed=4,
        preset_hands=[[debt], []],
        initial_phase=GamePhase.ACTION,
        records=replay_player.records_from_game(source),
    )

    assert [event.digest() for event in replayed.event_log] == [
        event.digest() for event in source.event_log
    ]


def test_replay_records_rejects_mismatched_digest() -> None:
    assert hasattr(replay_player, "ReplayRecord")
    record = replay_player.ReplayRecord(
        player_id="P1",
        action_payload={"type": "DrawCards"},
        before_digest=("bad",),
        after_digest=("also-bad",),
        event_digests=(),
    )

    try:
        replay_player.replay_records(player_count=2, seed=1, records=[record])
    except ValueError as error:
        assert "before digest mismatch" in str(error)
    else:
        raise AssertionError("Expected replay verification to reject mismatched digest")


def test_replay_records_runs_draw_from_official_deck() -> None:
    source = Game.new(player_count=2, seed=9)
    source.step("P1", DrawCards())

    replayed = replay_player.replay_records(
        player_count=2,
        seed=9,
        records=replay_player.records_from_game(source),
    )

    assert len(replayed.state.players["P1"].hand) == len(source.state.players["P1"].hand)


def test_replay_records_verifies_rent_response_and_payment_flow() -> None:
    hands = [
        [prop("blue-1", 4, PropertyColor.BLUE), rent("rent-blue", (PropertyColor.BLUE,))],
        [],
    ]
    source = Game.new(player_count=2, seed=10, preset_hands=hands)
    source.state.phase = GamePhase.ACTION

    source.step("P1", PlayProperty("blue-1", PropertyColor.BLUE))
    source.step("P1", PlayRent("rent-blue", target_player_id="P2", color=PropertyColor.BLUE))
    source.step("P2", RespondJustSayNo(card_id=None, accept=True))
    source.step("P2", PayWithAssets(card_ids=()))

    replayed = replay_player.replay_records(
        player_count=2,
        seed=10,
        preset_hands=hands,
        initial_phase=GamePhase.ACTION,
        records=replay_player.records_from_game(source),
    )

    assert [event.digest() for event in replayed.event_log] == [
        event.digest() for event in source.event_log
    ]
    assert replayed.state.pending_payment is None

from dbreaker.engine.actions import (
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
from dbreaker.engine.cards import (
    ACTION_COUNT_BY_SUBTYPE,
    RENT_LADDER_BY_COLOR,
    ActionSubtype,
    Card,
    CardKind,
    PropertyColor,
    create_standard_deck,
)
from dbreaker.engine.game import Game
from dbreaker.engine.payment import legal_payment_selections
from dbreaker.engine.player import PlayerState
from dbreaker.engine.rules import GamePhase, PropertyRearrangeTiming, RuleConfig


def card(
    card_id: str,
    kind: CardKind,
    value: int,
    *,
    color: PropertyColor | None = None,
    colors: tuple[PropertyColor, ...] = (),
    action_subtype: ActionSubtype | None = None,
) -> Card:
    return Card(
        id=card_id,
        name=card_id,
        kind=kind,
        value=value,
        color=color,
        colors=colors,
        action_subtype=action_subtype,
    )


def money(card_id: str, value: int) -> Card:
    return card(card_id, CardKind.MONEY, value)


def prop(card_id: str, value: int, color: PropertyColor) -> Card:
    return card(card_id, CardKind.PROPERTY, value, color=color)


def action(card_id: str, subtype: ActionSubtype, value: int = 3) -> Card:
    return card(card_id, CardKind.ACTION, value, action_subtype=subtype)


def rent(card_id: str, colors: tuple[PropertyColor, ...]) -> Card:
    return card(card_id, CardKind.RENT, 1, colors=colors)


def test_official_deck_has_expected_counts_and_metadata() -> None:
    deck = create_standard_deck()

    assert len(deck) == 106
    assert len({card.id for card in deck}) == len(deck)
    assert sum(card.kind == CardKind.MONEY for card in deck) == 20
    assert sum(card.kind == CardKind.PROPERTY for card in deck) == 28
    assert sum(card.kind == CardKind.WILD_PROPERTY for card in deck) == 11
    assert sum(card.kind == CardKind.RENT for card in deck) == 13
    assert sum(card.kind == CardKind.ACTION for card in deck) == 34
    assert RENT_LADDER_BY_COLOR[PropertyColor.BLUE] == (3, 8)
    assert ACTION_COUNT_BY_SUBTYPE[ActionSubtype.PASS_GO] == 10
    assert any(
        card.kind == CardKind.WILD_PROPERTY
        and card.value == 0
        and set(card.playable_colors) == set(RENT_LADDER_BY_COLOR)
        for card in deck
    )


def test_rule_config_includes_turn_limits_and_phases() -> None:
    rules = RuleConfig.from_mapping(
        {
            "starting_hand_size": 4,
            "draw_count": 3,
            "empty_hand_draw_count": 6,
            "hand_limit": 8,
            "actions_per_turn": 2,
            "property_rearrange_timing": "anytime_on_turn",
        }
    )

    assert rules.starting_hand_size == 4
    assert rules.draw_count == 3
    assert rules.empty_hand_draw_count == 6
    assert rules.hand_limit == 8
    assert rules.actions_per_turn == 2
    assert rules.property_rearrange_timing is PropertyRearrangeTiming.ANYTIME_ON_TURN


def test_turn_starts_with_draw_and_enforces_action_limit_then_discard() -> None:
    hand = [money("m1", 1), money("m2", 2), money("m3", 3)]
    draw_deck = [money(f"d{i}", 1) for i in range(8)]
    game = Game.new(player_count=2, seed=1, preset_hands=[hand, []])
    game.state.deck = draw_deck

    assert game.state.phase is GamePhase.DRAW
    assert game.legal_actions("P1") == [DrawCards()]
    assert game.step("P1", DrawCards()).accepted is True
    assert len(game.state.players["P1"].hand) == 5
    assert game.state.phase is GamePhase.ACTION

    assert game.step("P1", BankCard("m1")).accepted is True
    assert game.step("P1", BankCard("m2")).accepted is True
    assert game.step("P1", BankCard("m3")).accepted is True
    assert game.state.phase is GamePhase.DISCARD
    assert all(isinstance(action, DiscardCard | EndTurn) for action in game.legal_actions("P1"))


def test_empty_hand_draws_five_cards() -> None:
    game = Game.new(player_count=2, seed=1, preset_hands=[[], []])
    game.state.deck = [money(f"d{i}", 1) for i in range(6)]

    assert game.step("P1", DrawCards()).accepted is True

    assert len(game.state.players["P1"].hand) == 5


def test_payment_choices_allow_overpay_and_transfer_assets() -> None:
    game = Game.new(player_count=2, seed=1, preset_hands=[[], []])
    game.state.phase = GamePhase.PAYMENT
    game.state.players["P1"] = PlayerState(
        id="P1", name="P1", bank=[money("m2", 2), money("m5", 5)]
    )
    game.state.players["P2"] = PlayerState(
        id="P2",
        name="P2",
        properties={PropertyColor.BLUE: [prop("b1", 4, PropertyColor.BLUE)]},
    )
    game.state.set_pending_payment(payer_id="P1", receiver_id="P2", amount=3, reason="rent")

    selections = legal_payment_selections(game.state.players["P1"], amount=3)
    assert ("m5",) in [tuple(card.id for card in selection.cards) for selection in selections]

    assert game.step("P1", PayWithAssets(card_ids=("m5",))).accepted is True
    assert [card.id for card in game.state.players["P1"].bank] == ["m2"]
    assert [card.id for card in game.state.players["P2"].bank] == ["m5"]
    assert game.state.phase is GamePhase.ACTION


def test_payment_phase_has_legal_pay_actions_when_nine_one_dollar_bills_needed() -> None:
    """Regression: 8-card combo search must not leave PAYMENT with no legal pays."""
    game = Game.new(player_count=2, seed=1, preset_hands=[[], []])
    game.state.players["P1"] = PlayerState(
        id="P1",
        name="P1",
        bank=[money(f"bill-{i}", 1) for i in range(9)],
    )
    game.state.players["P2"] = PlayerState(id="P2", name="P2")
    game.state.set_pending_payment(payer_id="P1", receiver_id="P2", amount=9, reason="rent")

    actions = game.legal_actions("P1")
    assert len(actions) >= 1
    assert all(isinstance(a, PayWithAssets) for a in actions)
    assert any(len(a.card_ids) == 9 for a in actions)


def test_pay_property_preserves_color_for_receiver() -> None:
    game = Game.new(player_count=2, seed=1, preset_hands=[[], []])
    game.state.phase = GamePhase.PAYMENT
    game.state.players["P1"] = PlayerState(
        id="P1",
        name="P1",
        properties={PropertyColor.RED: [prop("r1", 3, PropertyColor.RED)]},
    )
    game.state.players["P2"] = PlayerState(id="P2", name="P2")
    game.state.set_pending_payment(payer_id="P1", receiver_id="P2", amount=2, reason="debt")

    assert game.step("P1", PayWithAssets(card_ids=("r1",))).accepted is True

    assert game.state.players["P1"].properties.get(PropertyColor.RED, []) == []
    assert [card.id for card in game.state.players["P2"].properties[PropertyColor.RED]] == ["r1"]


def test_wild_rearrange_and_building_restrictions_affect_rent() -> None:
    wild = card(
        "wild-bg",
        CardKind.WILD_PROPERTY,
        4,
        colors=(PropertyColor.BLUE, PropertyColor.GREEN),
    )
    cards = [
        prop("b1", 4, PropertyColor.BLUE),
        wild,
        action("house", ActionSubtype.HOUSE, 3),
        action("hotel", ActionSubtype.HOTEL, 4),
        rent("rent-bg", (PropertyColor.BLUE, PropertyColor.GREEN)),
    ]
    game = Game.new(
        player_count=2,
        seed=1,
        preset_hands=[cards, []],
        rules=RuleConfig(actions_per_turn=10),
    )
    game.state.phase = GamePhase.ACTION

    assert game.step("P1", PlayProperty("b1", PropertyColor.BLUE)).accepted is True
    assert game.step("P1", PlayProperty("wild-bg", PropertyColor.GREEN)).accepted is True
    assert game.step("P1", RearrangeProperty("wild-bg", PropertyColor.BLUE)).accepted is True
    assert game.step("P1", PlayActionCard("house", color=PropertyColor.BLUE)).accepted is True
    assert game.step("P1", PlayActionCard("hotel", color=PropertyColor.BLUE)).accepted is True
    assert [
        card.id for card in game.state.players["P1"].property_attachments[PropertyColor.BLUE]
    ] == [
        "house",
        "hotel",
    ]


def test_rent_uses_ladder_house_hotel_bonus_and_double_rent_pending_payment() -> None:
    cards = [
        prop("b1", 4, PropertyColor.BLUE),
        prop("b2", 4, PropertyColor.BLUE),
        action("house", ActionSubtype.HOUSE, 3),
        action("hotel", ActionSubtype.HOTEL, 4),
        rent("rent-blue-green", (PropertyColor.BLUE, PropertyColor.GREEN)),
        action("double", ActionSubtype.DOUBLE_THE_RENT, 1),
    ]
    game = Game.new(
        player_count=2,
        seed=1,
        preset_hands=[cards, []],
        rules=RuleConfig(actions_per_turn=10),
    )
    game.state.phase = GamePhase.ACTION
    game.state.players["P2"] = PlayerState(id="P2", name="P2", bank=[money("m10", 10)])

    for play in [
        PlayProperty("b1", PropertyColor.BLUE),
        PlayProperty("b2", PropertyColor.BLUE),
        PlayActionCard("house", color=PropertyColor.BLUE),
        PlayActionCard("hotel", color=PropertyColor.BLUE),
    ]:
        assert game.step("P1", play).accepted is True

    assert (
        game.step(
            "P1",
            PlayRent(
                "rent-blue-green",
                target_player_id="P2",
                color=PropertyColor.BLUE,
                double_rent_card_id="double",
            ),
        ).accepted
        is True
    )

    assert game.state.phase is GamePhase.RESPOND
    assert game.step("P2", RespondJustSayNo(card_id=None, accept=True)).accepted is True
    assert game.state.pending_payment is not None
    assert game.state.pending_payment.amount == 30


def test_action_cards_and_just_say_no_chain() -> None:
    p1_cards = [
        action("pass-go", ActionSubtype.PASS_GO, 1),
        action("debt", ActionSubtype.DEBT_COLLECTOR, 3),
        action("sly", ActionSubtype.SLY_DEAL, 3),
        action("forced", ActionSubtype.FORCED_DEAL, 3),
        action("breaker", ActionSubtype.DEAL_BREAKER, 5),
        action("no-p1", ActionSubtype.JUST_SAY_NO, 4),
    ]
    game = Game.new(
        player_count=2,
        seed=1,
        preset_hands=[p1_cards, [action("no-p2", ActionSubtype.JUST_SAY_NO, 4)]],
        rules=RuleConfig(actions_per_turn=10),
    )
    game.state.phase = GamePhase.ACTION
    game.state.deck = [money("draw-a", 1), money("draw-b", 2)]
    game.state.players["P1"].properties[PropertyColor.BLUE] = [
        prop("own-b1", 4, PropertyColor.BLUE),
        prop("own-b2", 4, PropertyColor.BLUE),
    ]
    game.state.players["P2"].bank = [money("target-money", 5)]
    game.state.players["P2"].properties[PropertyColor.RED] = [
        prop("target-r1", 3, PropertyColor.RED)
    ]
    game.state.players["P2"].properties[PropertyColor.GREEN] = [
        prop("target-g1", 4, PropertyColor.GREEN),
        prop("target-g2", 4, PropertyColor.GREEN),
        prop("target-g3", 4, PropertyColor.GREEN),
    ]

    assert game.step("P1", PlayActionCard("pass-go")).accepted is True
    assert {"draw-a", "draw-b"} <= {card.id for card in game.state.players["P1"].hand}

    assert game.step("P1", PlayActionCard("debt", target_player_id="P2")).accepted is True
    assert game.step("P2", RespondJustSayNo("no-p2", accept=False)).accepted is True
    assert game.step("P1", RespondJustSayNo("no-p1", accept=False)).accepted is True
    assert game.step("P2", RespondJustSayNo(None, accept=True)).accepted is True
    assert game.state.pending_payment is not None
    assert game.state.pending_payment.amount == 5

    assert game.step("P2", PayWithAssets(("target-money",))).accepted is True
    assert game.step(
        "P1", PlayActionCard("sly", target_player_id="P2", target_card_id="target-r1")
    ).accepted
    assert game.step("P2", RespondJustSayNo(None, accept=True)).accepted is True
    assert [card.id for card in game.state.players["P1"].properties[PropertyColor.RED]] == [
        "target-r1"
    ]
    assert (
        game.step(
            "P1",
            PlayActionCard(
                "forced",
                target_player_id="P2",
                offered_card_id="own-b1",
                requested_card_id="target-g1",
            ),
        ).accepted
        is False
    )
    assert (
        game.step(
            "P1",
            PlayActionCard("breaker", target_player_id="P2", color=PropertyColor.GREEN),
        ).accepted
        is True
    )
    assert game.step("P2", RespondJustSayNo(None, accept=True)).accepted is True
    assert game.state.players["P2"].properties.get(PropertyColor.GREEN, []) == []
    assert {card.id for card in game.state.players["P1"].properties[PropertyColor.GREEN]} == {
        "target-g1",
        "target-g2",
        "target-g3",
    }


def test_its_my_birthday_charges_each_opponent_two() -> None:
    birthday = action("birthday", ActionSubtype.ITS_MY_BIRTHDAY, 2)
    game = Game.new(
        player_count=4,
        seed=1,
        preset_hands=[
            [birthday, money("m1", 1)],
            [],
            [],
            [],
        ],
        rules=RuleConfig(actions_per_turn=10),
    )
    for pid, bill_id in (("P2", "p2pay"), ("P3", "p3pay"), ("P4", "p4pay")):
        p = game.state.players[pid]
        game.state.players[pid] = p.add_to_bank(money(bill_id, 2))
    game.state.phase = GamePhase.ACTION

    assert any(
        isinstance(a, PlayActionCard) and a.card_id == "birthday"
        for a in game.legal_actions("P1")
    )
    assert game.step("P1", PlayActionCard("birthday")).accepted is True
    assert game.state.phase is GamePhase.PAYMENT
    assert game.state.pending_payment is not None
    assert game.state.pending_payment.payer_id == "P2"
    assert game.state.pending_payment.amount == 2
    assert game.state.pending_payment.receiver_id == "P1"

    assert game.step("P2", PayWithAssets(("p2pay",))).accepted is True
    assert game.state.phase is GamePhase.PAYMENT
    assert game.state.pending_payment.payer_id == "P3"

    assert game.step("P3", PayWithAssets(("p3pay",))).accepted is True
    assert game.state.pending_payment.payer_id == "P4"

    assert game.step("P4", PayWithAssets(("p4pay",))).accepted is True
    assert game.state.phase is GamePhase.ACTION
    assert game.state.pending_payment is None
    assert not game.state.pending_payment_queue

    assert sum(card.value for card in game.state.players["P1"].bank) == 6
    assert any(card.id == "birthday" for card in game.state.discard)
    assert game.state.actions_taken == 1


def test_empty_property_color_does_not_generate_rent_action() -> None:
    rent_card = rent("rent-ru", (PropertyColor.RAILROAD, PropertyColor.UTILITY))
    game = Game.new(player_count=2, seed=1, preset_hands=[[rent_card], []])
    game.state.players["P1"].properties = {PropertyColor.UTILITY: []}
    game.state.phase = GamePhase.ACTION

    legal = game.legal_actions("P1")
    assert not any(
        isinstance(a, PlayRent) and a.color == PropertyColor.UTILITY for a in legal
    )


def test_rearrange_stall_cap_rejects_unbroken_chain() -> None:
    wild = card(
        "wild-bg",
        CardKind.WILD_PROPERTY,
        4,
        colors=(PropertyColor.BLUE, PropertyColor.GREEN),
    )
    game = Game.new(
        player_count=2,
        seed=1,
        preset_hands=[[], []],
        rules=RuleConfig(
            actions_per_turn=10,
            max_consecutive_rearranges=3,
            property_rearrange_timing=PropertyRearrangeTiming.ANYTIME_ON_TURN,
        ),
    )
    game.state.players["P1"] = PlayerState(
        id="P1", name="P1", hand=[], properties={PropertyColor.GREEN: [wild]}
    )
    game.state.phase = GamePhase.ACTION

    assert game.step("P1", RearrangeProperty("wild-bg", PropertyColor.BLUE)).accepted is True
    assert game.step("P1", RearrangeProperty("wild-bg", PropertyColor.GREEN)).accepted is True
    assert game.step("P1", RearrangeProperty("wild-bg", PropertyColor.BLUE)).accepted is True
    assert game.state.consecutive_rearranges == 3
    assert game.step("P1", RearrangeProperty("wild-bg", PropertyColor.GREEN)).accepted is False
    assert not any(
        isinstance(a, RearrangeProperty) and a.card_id == "wild-bg"
        for a in game.legal_actions("P1")
    )


def test_counted_action_resets_rearrange_streak() -> None:
    wild = card(
        "wild-bg",
        CardKind.WILD_PROPERTY,
        4,
        colors=(PropertyColor.BLUE, PropertyColor.GREEN),
    )
    bill = money("m1", 1)
    game = Game.new(
        player_count=2,
        seed=1,
        preset_hands=[[], []],
        rules=RuleConfig(
            actions_per_turn=10,
            max_consecutive_rearranges=3,
            property_rearrange_timing=PropertyRearrangeTiming.ANYTIME_ON_TURN,
        ),
    )
    game.state.players["P1"] = PlayerState(
        id="P1", name="P1", hand=[bill], properties={PropertyColor.GREEN: [wild]}
    )
    game.state.phase = GamePhase.ACTION

    assert game.step("P1", RearrangeProperty("wild-bg", PropertyColor.BLUE)).accepted is True
    assert game.step("P1", RearrangeProperty("wild-bg", PropertyColor.GREEN)).accepted is True
    assert game.step("P1", RearrangeProperty("wild-bg", PropertyColor.BLUE)).accepted is True
    assert game.state.consecutive_rearranges == 3
    assert game.step("P1", BankCard("m1")).accepted is True
    assert game.state.consecutive_rearranges == 0
    assert game.step("P1", RearrangeProperty("wild-bg", PropertyColor.GREEN)).accepted is True

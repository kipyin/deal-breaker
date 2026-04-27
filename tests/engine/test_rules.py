from dbreaker.engine.rules import PropertyRearrangeTiming, RentWildPropertyMode, RuleConfig


def test_official_rules_are_default() -> None:
    rules = RuleConfig.official()

    assert rules.allow_just_say_no_chain is True
    assert rules.rent_with_wild_property is RentWildPropertyMode.OFFICIAL
    assert rules.property_rearrange_timing is PropertyRearrangeTiming.BEFORE_ACTION
    assert rules.reshuffle_discard_when_deck_empty is True


def test_rule_config_loads_yaml_style_mapping() -> None:
    rules = RuleConfig.from_mapping(
        {
            "allow_just_say_no_chain": False,
            "rent_with_wild_property": "never",
            "property_rearrange_timing": "anytime_on_turn",
            "reshuffle_discard_when_deck_empty": False,
        }
    )

    assert rules.allow_just_say_no_chain is False
    assert rules.rent_with_wild_property is RentWildPropertyMode.NEVER
    assert rules.property_rearrange_timing is PropertyRearrangeTiming.ANYTIME_ON_TURN
    assert rules.reshuffle_discard_when_deck_empty is False

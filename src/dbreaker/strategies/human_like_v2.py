from __future__ import annotations

from dbreaker.strategies.human_like import HumanLikeStrategy


class HumanLikeV2Strategy(HumanLikeStrategy):
    """Same policy as ``human_like``; distinct registry name for evaluation / baselines."""

    name = "human_like_v2"

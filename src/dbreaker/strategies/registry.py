from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from pathlib import Path

from dbreaker.strategies.aggressive import AggressiveStrategy
from dbreaker.strategies.base import BaseStrategy
from dbreaker.strategies.defensive import DefensiveStrategy
from dbreaker.strategies.heuristic import BasicHeuristicStrategy
from dbreaker.strategies.human_like import HumanLikeStrategy
from dbreaker.strategies.omniscient import OmniscientBaselineStrategy
from dbreaker.strategies.random import RandomStrategy
from dbreaker.strategies.set_completion import SetCompletionStrategy

StrategyFactory = Callable[[], BaseStrategy]


class StrategyRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, StrategyFactory] = {}

    def register(self, name: str, factory: StrategyFactory) -> None:
        self._factories[name] = factory

    def create(self, name: str) -> BaseStrategy:
        try:
            return self._factories[name]()
        except KeyError as exc:
            known = ", ".join(sorted(self._factories))
            raise KeyError(f"Unknown strategy '{name}'. Known strategies: {known}") from exc

    def names(self) -> list[str]:
        return sorted(self._factories)


def default_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(RandomStrategy.name, RandomStrategy)
    registry.register(BasicHeuristicStrategy.name, BasicHeuristicStrategy)
    registry.register(AggressiveStrategy.name, AggressiveStrategy)
    registry.register(DefensiveStrategy.name, DefensiveStrategy)
    registry.register(SetCompletionStrategy.name, SetCompletionStrategy)
    registry.register(OmniscientBaselineStrategy.name, OmniscientBaselineStrategy)
    registry.register(HumanLikeStrategy.name, HumanLikeStrategy)
    return registry


def create_strategy(spec: str, registry: StrategyRegistry | None = None) -> BaseStrategy:
    if spec.startswith("neural:"):
        checkpoint = spec.removeprefix("neural:")
        if not checkpoint:
            raise ValueError("neural strategy spec must include a checkpoint path")
        neural_module = import_module("dbreaker.strategies.neural")
        return neural_module.NeuralStrategy(Path(checkpoint))
    return (registry or default_registry()).create(spec)

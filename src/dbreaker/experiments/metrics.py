from __future__ import annotations

from dataclasses import dataclass

from dbreaker.experiments.runner import GameResult


@dataclass(frozen=True, slots=True)
class StrategySummary:
    strategy: str
    games: int
    wins: int
    average_rank: float

    @property
    def win_rate(self) -> float:
        if self.games == 0:
            return 0.0
        return self.wins / self.games


def summarize_results(results: list[GameResult]) -> dict[str, StrategySummary]:
    ranks: dict[str, list[int]] = {}
    wins: dict[str, int] = {}
    for result in results:
        for rank, strategy in enumerate(result.rankings, start=1):
            ranks.setdefault(strategy, []).append(rank)
            wins.setdefault(strategy, 0)
            if rank == 1 and result.ended_by == "winner":
                wins[strategy] += 1

    return {
        strategy: StrategySummary(
            strategy=strategy,
            games=len(strategy_ranks),
            wins=wins[strategy],
            average_rank=sum(strategy_ranks) / len(strategy_ranks),
        )
        for strategy, strategy_ranks in ranks.items()
    }

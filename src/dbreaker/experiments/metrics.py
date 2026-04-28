from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from dbreaker.experiments.runner import GameEndReason, GameResult


@dataclass(frozen=True, slots=True)
class StrategySummary:
    strategy: str
    games: int
    wins: int
    average_rank: float
    games_winner_outcome: int = 0
    games_max_turns: int = 0
    games_stalemate: int = 0
    games_aborted: int = 0

    @property
    def win_rate(self) -> float:
        if self.games == 0:
            return 0.0
        return self.wins / self.games

    @property
    def aborted_rate(self) -> float:
        if self.games == 0:
            return 0.0
        return self.games_aborted / self.games

    @property
    def stalemate_rate(self) -> float:
        if self.games == 0:
            return 0.0
        return self.games_stalemate / self.games

    @property
    def max_turn_rate(self) -> float:
        if self.games == 0:
            return 0.0
        return self.games_max_turns / self.games

    def outcome_counts(self) -> dict[GameEndReason, int]:
        """Per-game outcome tallies for this strategy (sum to ``games``)."""
        return {
            "winner": self.games_winner_outcome,
            "max_turns": self.games_max_turns,
            "stalemate": self.games_stalemate,
            "aborted": self.games_aborted,
        }


def summarize_results(results: list[GameResult]) -> dict[str, StrategySummary]:
    ranks: dict[str, list[int]] = {}
    wins: dict[str, int] = defaultdict(int)
    outcome_tally: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int),
    )
    for result in results:
        ended = result.ended_by
        for rank, strategy in enumerate(result.rankings, start=1):
            ranks.setdefault(strategy, []).append(rank)
            outcome_tally[strategy][ended] += 1
            if rank == 1 and ended == "winner":
                wins[strategy] += 1

    summaries: dict[str, StrategySummary] = {}
    for strategy, strategy_ranks in ranks.items():
        ot = outcome_tally[strategy]
        summaries[strategy] = StrategySummary(
            strategy=strategy,
            games=len(strategy_ranks),
            wins=wins[strategy],
            average_rank=sum(strategy_ranks) / len(strategy_ranks),
            games_winner_outcome=int(ot.get("winner", 0)),
            games_max_turns=int(ot.get("max_turns", 0)),
            games_stalemate=int(ot.get("stalemate", 0)),
            games_aborted=int(ot.get("aborted", 0)),
        )
    return summaries

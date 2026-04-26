from __future__ import annotations

from dataclasses import dataclass

from dbreaker.experiments.metrics import StrategySummary


@dataclass(frozen=True, slots=True)
class TournamentReport:
    summaries: dict[str, StrategySummary]
    ratings: dict[str, float]
    matrix: dict[str, dict[str, float]]

    def to_markdown(self) -> str:
        lines = [
            "# Tournament Report",
            "",
            "| Strategy | Games | Wins | Win Rate | Avg Rank | Elo |",
        ]
        lines.append("|---|---:|---:|---:|---:|---:|")
        for name in sorted(self.summaries):
            summary = self.summaries[name]
            lines.append(
                f"| {name} | {summary.games} | {summary.wins} | "
                f"{summary.win_rate:.2%} | {summary.average_rank:.2f} | "
                f"{self.ratings.get(name, 1000.0):.1f} |"
            )
        return "\n".join(lines)

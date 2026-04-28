from __future__ import annotations

from dataclasses import dataclass

from dbreaker.experiments.eval_protocol import EVAL_PROTOCOL_REVISION
from dbreaker.experiments.metrics import StrategySummary


@dataclass(frozen=True, slots=True)
class TournamentReport:
    summaries: dict[str, StrategySummary]
    ratings: dict[str, float]
    matrix: dict[str, dict[str, float]]
    games_with_winner: int
    games_max_turn: int
    games_stalemate: int
    games_aborted: int
    max_turns_cap: int

    def to_markdown(self) -> str:
        total = (
            self.games_with_winner
            + self.games_max_turn
            + self.games_stalemate
            + self.games_aborted
        )
        lines = [
            "# Tournament Report",
            "",
            f"Evaluation protocol revision: `{EVAL_PROTOCOL_REVISION}`",
            "",
            f"Outcomes: {self.games_with_winner} completed with a property-set winner, "
            f"{self.games_max_turn} hit max turns (cap {self.max_turns_cap}), "
            f"{self.games_stalemate} stalemates (no progress for N turns), "
            f"{self.games_aborted} aborted.",
            f"({total} game(s) total in this report.)" if total else "(no games run.)",
            "",
            "| Strategy | Games | Wins* | Win Rate | Avg Rank | Elo | Abort% | Stalemate% | MaxTurn% |",
        ]
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for name in sorted(self.summaries):
            summary = self.summaries[name]
            lines.append(
                f"| {name} | {summary.games} | {summary.wins} | "
                f"{summary.win_rate:.2%} | {summary.average_rank:.2f} | "
                f"{self.ratings.get(name, 1000.0):.1f} | "
                f"{summary.aborted_rate:.1%} | {summary.stalemate_rate:.1%} | "
                f"{summary.max_turn_rate:.1%} |"
            )
        lines.append("")
        lines.append(
            "*Wins = games ended by completing the required number of full property "
            "sets, not max-turn, stalemate, or aborted placings."
        )
        return "\n".join(lines)

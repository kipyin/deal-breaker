from __future__ import annotations

from typing import Any

from dbreaker.experiments.reports import TournamentReport
from dbreaker.experiments.rl_search import EvaluationResult


def tournament_report_to_dict(report: TournamentReport) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for name, s in report.summaries.items():
        summaries[name] = {
            "strategy": s.strategy,
            "games": s.games,
            "wins": s.wins,
            "average_rank": s.average_rank,
            "win_rate": s.win_rate,
        }
    return {
        "summaries": summaries,
        "ratings": dict(report.ratings),
        "matrix": {a: dict(b) for a, b in report.matrix.items()},
        "games_with_winner": report.games_with_winner,
        "games_max_turn": report.games_max_turn,
        "games_stalemate": report.games_stalemate,
        "games_aborted": report.games_aborted,
        "max_turns_cap": report.max_turns_cap,
    }


def evaluation_result_to_dict(result: EvaluationResult) -> dict[str, Any]:
    return {
        "player_count": result.player_count,
        "candidate": result.candidate,
        "baselines": list(result.baselines),
        "previous_champion": result.previous_champion,
        "report": tournament_report_to_dict(result.report),
        "candidate_score": result.candidate_score,
        "strategy_scores": dict(result.strategy_scores),
        "total_games": result.total_games,
        "aborted_rate": result.aborted_rate,
        "stalemate_rate": result.stalemate_rate,
        "max_turn_rate": result.max_turn_rate,
    }

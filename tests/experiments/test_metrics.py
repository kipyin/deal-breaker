from dbreaker.experiments.metrics import summarize_results
from dbreaker.experiments.runner import GameResult


def test_summarize_results_reports_win_rate_and_average_rank() -> None:
    results = [
        GameResult(game_id="g1", rankings=["random", "basic"], turns=10),
        GameResult(game_id="g2", rankings=["basic", "random"], turns=12),
        GameResult(game_id="g3", rankings=["random", "basic"], turns=9),
    ]

    summary = summarize_results(results)

    assert summary["random"].wins == 2
    assert summary["random"].games == 3
    assert summary["random"].win_rate == 2 / 3
    assert summary["basic"].average_rank == 5 / 3

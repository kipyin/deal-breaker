from __future__ import annotations

import json
from pathlib import Path

import pytest

from dbreaker.experiments.metrics import StrategySummary
from dbreaker.experiments.reports import TournamentReport
from dbreaker.experiments.rl_search import (
    ChampionEntry,
    EvaluationConfig,
    RLSearchConfig,
    evaluate_candidate,
    load_champions_manifest,
    promote_champion,
    run_rl_search,
    write_champions_manifest,
)
from dbreaker.ml.trainer import PPOConfig, TrainingStats


def _report(
    *,
    candidate: str,
    champion: str | None = None,
    candidate_rank: float = 1.4,
    champion_rank: float = 2.0,
    aborted: int = 0,
) -> TournamentReport:
    summaries = {
        candidate: StrategySummary(candidate, games=6, wins=3, average_rank=candidate_rank),
        "basic": StrategySummary("basic", games=6, wins=1, average_rank=2.7),
        "aggressive": StrategySummary("aggressive", games=6, wins=1, average_rank=2.5),
    }
    ratings = {candidate: 1040.0, "basic": 980.0, "aggressive": 990.0}
    if champion is not None:
        summaries[champion] = StrategySummary(champion, games=6, wins=1, average_rank=champion_rank)
        ratings[champion] = 1000.0
    return TournamentReport(
        summaries=summaries,
        ratings=ratings,
        matrix={},
        games_with_winner=6 - aborted,
        games_max_turn=0,
        games_stalemate=0,
        games_aborted=aborted,
        max_turns_cap=50,
    )


def test_run_rl_search_trains_each_requested_count_and_writes_manifests(tmp_path: Path) -> None:
    calls: list[tuple[PPOConfig, Path, int]] = []

    def train_fn(
        config: PPOConfig,
        *,
        checkpoint_out: Path | None = None,
        seed: int | None = None,
        **_: object,
    ) -> TrainingStats:
        assert checkpoint_out is not None
        assert seed is not None
        calls.append((config, checkpoint_out, seed))
        checkpoint_out.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_out.write_text("checkpoint", encoding="utf-8")
        return TrainingStats(
            games=config.games,
            steps=config.player_count * 10,
            mean_reward=config.player_count / 10,
            checkpoint_path=str(checkpoint_out),
        )

    manifests = run_rl_search(
        RLSearchConfig(
            output_dir=tmp_path / "rl-search",
            player_counts=(2, 4),
            runs_per_count=2,
            games_per_run=3,
            seed=100,
            max_turns=7,
            max_self_play_steps=80,
            update_epochs=1,
        ),
        train_fn=train_fn,
    )

    assert [m.player_count for m in manifests] == [2, 2, 4, 4]
    assert [call[0].player_count for call in calls] == [2, 2, 4, 4]
    assert [call[0].games for call in calls] == [3, 3, 3, 3]
    assert [call[0].max_turns for call in calls] == [7, 7, 7, 7]
    assert len({call[2] for call in calls}) == 4
    assert (tmp_path / "rl-search" / "2p" / "run-001.json").exists()
    assert manifests[0].checkpoint_path == str(tmp_path / "rl-search" / "2p" / "run-001.pt")

    manifest_payload = json.loads(
        (tmp_path / "rl-search" / "4p" / "run-002.json").read_text(encoding="utf-8")
    )
    assert manifest_payload["player_count"] == 4
    assert manifest_payload["training"]["steps"] == 40
    assert manifest_payload["feature_schema"]


def test_run_rl_search_rejects_invalid_player_counts(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="player counts must be between 2 and 5"):
        run_rl_search(RLSearchConfig(output_dir=tmp_path, player_counts=(1, 6)))


def test_evaluate_candidate_uses_baselines_and_existing_champion(
    tmp_path: Path,
) -> None:
    champions_path = tmp_path / "champions.json"
    write_champions_manifest(
        champions_path,
        {
            4: ChampionEntry(
                player_count=4,
                checkpoint_path="checkpoints/rl-search/champions/4p.pt",
                evaluation_score=1010.0,
                metadata={"source": "previous"},
            )
        },
    )
    calls: list[dict[str, object]] = []

    def tournament_fn(**kwargs: object) -> TournamentReport:
        calls.append(kwargs)
        return _report(
            candidate="neural:new.pt",
            champion="neural:checkpoints/rl-search/champions/4p.pt",
        )

    result = evaluate_candidate(
        EvaluationConfig(
            player_count=4,
            candidate="neural:new.pt",
            champions_path=champions_path,
            baselines=("basic", "aggressive"),
            games=11,
            seed=33,
            max_turns=50,
            max_self_play_steps=90,
        ),
        tournament_fn=tournament_fn,
    )

    assert calls == [
        {
            "player_count": 4,
            "games": 11,
            "strategy_names": [
                "neural:new.pt",
                "basic",
                "aggressive",
                "neural:checkpoints/rl-search/champions/4p.pt",
            ],
            "seed": 33,
            "max_turns": 50,
            "max_self_play_steps": 90,
        }
    ]
    assert result.player_count == 4
    assert result.previous_champion == "neural:checkpoints/rl-search/champions/4p.pt"
    assert result.candidate_score > result.strategy_scores["basic"]


def test_evaluate_candidate_rejects_missing_candidate_or_baseline_results() -> None:
    missing_candidate = TournamentReport(
        summaries={"basic": StrategySummary("basic", games=1, wins=1, average_rank=1.0)},
        ratings={"basic": 1000.0},
        matrix={},
        games_with_winner=1,
        games_max_turn=0,
        games_stalemate=0,
        games_aborted=0,
        max_turns_cap=50,
    )

    with pytest.raises(ValueError, match="missing tournament summaries"):
        evaluate_candidate(
            EvaluationConfig(player_count=2, candidate="neural:new.pt", baselines=("basic",)),
            tournament_fn=lambda **_: missing_candidate,
        )


def test_evaluate_candidate_rejects_non_positive_games() -> None:
    with pytest.raises(ValueError, match="games must be at least 1"):
        evaluate_candidate(EvaluationConfig(player_count=2, candidate="neural:new.pt", games=0))


def test_promote_champion_updates_manifest_when_candidate_beats_baselines_and_champion(
    tmp_path: Path,
) -> None:
    champions_path = tmp_path / "champions.json"
    write_champions_manifest(
        champions_path,
        {
            2: ChampionEntry(
                player_count=2,
                checkpoint_path="old.pt",
                evaluation_score=1000.0,
                metadata={"aborted_rate": 0.0, "stalemate_rate": 0.0, "max_turn_rate": 0.0},
            )
        },
    )
    evaluation = evaluate_candidate(
        EvaluationConfig(player_count=2, candidate="neural:new.pt", baselines=("basic",)),
        tournament_fn=lambda **_: _report(candidate="neural:new.pt", champion="neural:old.pt"),
    )

    decision = promote_champion(
        champions_path,
        evaluation,
        checkpoint_path="new.pt",
        metadata={"run": "run-001"},
    )

    champions = load_champions_manifest(champions_path)
    assert decision.promoted is True
    assert champions[2] is not None
    assert champions[2].checkpoint_path == "new.pt"
    payload = json.loads(champions_path.read_text(encoding="utf-8"))
    assert sorted(payload["champions"]) == ["2", "3", "4", "5"]


def test_promote_champion_requires_current_champion_in_evaluation(tmp_path: Path) -> None:
    champions_path = tmp_path / "champions.json"
    write_champions_manifest(
        champions_path,
        {
            5: ChampionEntry(
                player_count=5,
                checkpoint_path="old.pt",
                evaluation_score=900.0,
                metadata={"aborted_rate": 0.0, "stalemate_rate": 0.0, "max_turn_rate": 0.0},
            )
        },
    )
    evaluation = evaluate_candidate(
        EvaluationConfig(player_count=5, candidate="neural:new.pt", baselines=("basic",)),
        tournament_fn=lambda **_: _report(candidate="neural:new.pt"),
    )

    decision = promote_champion(champions_path, evaluation, checkpoint_path="new.pt")

    assert decision.promoted is False
    assert "champion_gate:" in decision.reason
    assert load_champions_manifest(champions_path)[5].checkpoint_path == "old.pt"


def test_promote_champion_rejects_excessive_aborted_games(tmp_path: Path) -> None:
    champions_path = tmp_path / "champions.json"
    write_champions_manifest(champions_path, {})
    evaluation = evaluate_candidate(
        EvaluationConfig(player_count=3, candidate="neural:risky.pt", baselines=("basic",)),
        tournament_fn=lambda **_: _report(candidate="neural:risky.pt", aborted=2),
    )

    decision = promote_champion(
        champions_path,
        evaluation,
        checkpoint_path="risky.pt",
        max_aborted_rate=0.1,
    )

    assert decision.promoted is False
    assert "aborted_rate:" in decision.reason
    assert load_champions_manifest(champions_path)[3] is None

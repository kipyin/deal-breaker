from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WebConfig:
    """Runtime paths for the web stack."""

    data_root: Path
    artifact_root: Path

    @property
    def sqlite_path(self) -> Path:
        return self.data_root / "dbreaker.sqlite3"

    def ensure_dirs(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        (self.artifact_root / "replays").mkdir(parents=True, exist_ok=True)
        (self.artifact_root / "jobs").mkdir(parents=True, exist_ok=True)
        (self.artifact_root / "checkpoints").mkdir(parents=True, exist_ok=True)
        (self.artifact_root / "evaluations").mkdir(parents=True, exist_ok=True)
        (self.artifact_root / "imports").mkdir(parents=True, exist_ok=True)

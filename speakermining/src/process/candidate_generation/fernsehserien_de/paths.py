from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FernsehserienPaths:
    repo_root: Path

    @property
    def runtime_root(self) -> Path:
        return self.repo_root / "data" / "20_candidate_generation" / "fernsehserien_de"

    @property
    def chunks_dir(self) -> Path:
        return self.runtime_root / "chunks"

    @property
    def projections_dir(self) -> Path:
        return self.runtime_root / "projections"

    @property
    def cache_pages_dir(self) -> Path:
        return self.runtime_root / "cache" / "pages"

    @property
    def eventhandler_csv(self) -> Path:
        return self.runtime_root / "eventhandler.csv"

    def ensure(self) -> None:
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.projections_dir.mkdir(parents=True, exist_ok=True)
        self.cache_pages_dir.mkdir(parents=True, exist_ok=True)

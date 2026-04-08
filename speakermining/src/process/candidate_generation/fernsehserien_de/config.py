from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FernsehserienRunConfig:
    """Runtime configuration for fernsehserien.de retrieval."""

    repo_root: Path
    query_delay_seconds: float = 1.0
    max_network_calls: int = 1
    max_programs: int | None = None
    allow_network: bool = True
    fallback_traversal_policy: str = "on_gap"
    user_agent: str = "speaker-mining/0.1 (fernsehserien-stage2) python/3"

    @property
    def notebook_id(self) -> str:
        return "notebook_22_candidate_generation_fernsehserien_de"

    @property
    def unlimited_network_budget(self) -> bool:
        return int(self.max_network_calls) < 0

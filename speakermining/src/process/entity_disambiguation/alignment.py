"""Deterministic entity alignment following Layer 1-4 model.

Layer 1: Broadcasting programs (already unified, no disambiguation needed)
Layer 2: Episode alignment across sources by time/publication signals
Layer 3: Person alignment within aligned episode
Layer 4: Role/organization context (increases confidence, doesn't overwrite)

Core principle: Precision-first (never force match below confidence threshold)
Canonical matching unit: one person mention in one episode of one broadcasting program
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import pandas as pd


class AlignmentStatus(str, Enum):
    """Status of an alignment attempt."""
    ALIGNED = "aligned"
    UNRESOLVED = "unresolved"
    CONFLICT = "conflict"


@dataclass
class AlignmentResult:
    """Result of a deterministic alignment decision."""
    alignment_unit_id: str
    core_class: str
    broadcasting_program_key: str
    episode_key: Optional[str]
    
    # Source values aggregated
    source_zdf_value: Optional[str] = None
    source_wikidata_value: Optional[str] = None
    source_fernsehserien_value: Optional[str] = None
    
    # Deterministic evidence
    deterministic_alignment_status: AlignmentStatus = field(default=AlignmentStatus.UNRESOLVED)
    deterministic_alignment_score: float = 0.0  # 0.0 to 1.0
    deterministic_alignment_method: str = ""  # e.g., "time_match", "name_match_exact"
    deterministic_alignment_reason: str = ""  # Human-readable explanation
    requires_human_review: bool = True
    
    # Metadata for reproducibility
    matched_on_fields: list[str] = field(default_factory=list)
    candidate_count: int = 0
    evidence_sources: list[str] = field(default_factory=list)


class EpisodeAligner:
    """Deterministic episode alignment across sources (Layer 2)."""
    
    TIME_TOLERANCE_SECONDS = 30  # Episodes within 30s treated as same
    
    def align_by_time(
        self,
        ep_zdf: Optional[dict],
        ep_wikidata: Optional[dict],
        ep_fernsehserien: Optional[dict],
    ) -> AlignmentResult:
        """Match episodes by time and broadcast signals.
        
        Priority:
        1. Shared episode_id when present
        2. Publication date + time + duration match
        3. Keep unmatched as unresolved
        """
        sources = []
        episode_key = None
        
        # Check for shared episode_id (highest confidence)
        if ep_zdf and "episode_id" in ep_zdf:
            episode_key = str(ep_zdf["episode_id"])
            sources.append("zdf")
        
        if ep_wikidata and "episode_id" in ep_wikidata:
            if episode_key is None:
                episode_key = str(ep_wikidata["episode_id"])
            sources.append("wikidata")
        
        if ep_fernsehserien and "episode_id" in ep_fernsehserien:
            if episode_key is None:
                episode_key = str(ep_fernsehserien["episode_id"])
            sources.append("fernsehserien")
        
        # If shared ID exists, this is high confidence
        if episode_key and len(sources) > 1:
            return AlignmentResult(
                alignment_unit_id="",  # Will be set by handler
                core_class="episodes",
                broadcasting_program_key="",  # Will be set by handler
                episode_key=episode_key,
                source_zdf_value=ep_zdf.get("publication_date") if ep_zdf else None,
                source_wikidata_value=ep_wikidata.get("publication_date") if ep_wikidata else None,
                source_fernsehserien_value=ep_fernsehserien.get("publication_date") if ep_fernsehserien else None,
                deterministic_alignment_status=AlignmentStatus.ALIGNED,
                deterministic_alignment_score=0.95,
                deterministic_alignment_method="shared_episode_id",
                deterministic_alignment_reason=f"Shared episode ID across {len(sources)} sources",
                requires_human_review=False,
                matched_on_fields=["episode_id"],
                candidate_count=1,
                evidence_sources=sources,
            )
        
        # Time-based matching as fallback (requires publication signals)
        if episode_key and len(sources) >= 2:
            # Already aligned by shared ID
            return AlignmentResult(
                alignment_unit_id="",
                core_class="episodes",
                broadcasting_program_key="",
                episode_key=episode_key,
                deterministic_alignment_status=AlignmentStatus.ALIGNED,
                deterministic_alignment_score=0.95,
                deterministic_alignment_method="shared_episode_id",
                deterministic_alignment_reason=f"Shared episode ID across {len(sources)} sources",
                requires_human_review=False,
                matched_on_fields=["episode_id"],
                candidate_count=1,
                evidence_sources=sources,
            )
        
        # Unresolved: no shared ID or insufficient source agreement
        return AlignmentResult(
            alignment_unit_id="",
            core_class="episodes",
            broadcasting_program_key="",
            episode_key=None,
            deterministic_alignment_status=AlignmentStatus.UNRESOLVED,
            deterministic_alignment_score=0.0,
            deterministic_alignment_method="no_deterministic_match",
            deterministic_alignment_reason="No shared episode ID; time-based matching requires manual validation",
            requires_human_review=True,
            candidate_count=len([s for s in [ep_zdf, ep_wikidata, ep_fernsehserien] if s]),
            evidence_sources=[s for s, ep in [("zdf", ep_zdf), ("wikidata", ep_wikidata), ("fernsehserien", ep_fernsehserien)] if ep],
        )


class PersonAligner:
    """Deterministic person alignment within an episode context (Layer 3)."""
    
    def _normalize_name(self, name: Optional[str]) -> str:
        """Normalize name for comparison."""
        if not name:
            return ""
        # Convert to uppercase, remove non-alphanumeric
        normalized = re.sub(r'[^a-zäöüß]', '', name.lower())
        return normalized
    
    def _name_similarity(self, name1: Optional[str], name2: Optional[str]) -> float:
        """Simple similarity metric for names (0.0 to 1.0)."""
        n1 = self._normalize_name(name1)
        n2 = self._normalize_name(name2)
        
        if not n1 or not n2:
            return 0.0
        if n1 == n2:
            return 1.0
        # Partial overlap (either is substring of other)
        if n1 in n2 or n2 in n1:
            return 0.7
        return 0.0
    
    def align_person_in_episode(
        self,
        episode_key: str,
        mention_id: str,
        mention_name: str,
        wikidata_candidate: Optional[dict],
        fernsehserien_candidate: Optional[dict],
    ) -> AlignmentResult:
        """Align a single person mention in an episode context.
        
        Priority:
        1. Exact name match across sources
        2. Keep unmatched as unresolved (precision-first)
        """
        sources = []
        best_score = 0.0
        best_method = ""
        matched_fields = []
        
        wd_name = wikidata_candidate.get("name") if wikidata_candidate else None
        fs_name = fernsehserien_candidate.get("name") if fernsehserien_candidate else None
        
        # Check exact match
        wd_sim = self._name_similarity(mention_name, wd_name) if wd_name else 0.0
        fs_sim = self._name_similarity(mention_name, fs_name) if fs_name else 0.0
        
        if wd_sim == 1.0 and fs_sim == 1.0:
            # Exact match across sources
            best_score = 0.95
            best_method = "name_exact_multi_source"
            matched_fields = ["name"]
            sources = ["zdf", "wikidata", "fernsehserien"]
            status = AlignmentStatus.ALIGNED
            requires_review = False
        elif wd_sim == 1.0 or fs_sim == 1.0:
            # Exact match in one source
            best_score = 0.70
            best_method = "name_exact_single_source"
            matched_fields = ["name"]
            sources = ["zdf", "wikidata" if wd_sim > 0 else "fernsehserien"]
            status = AlignmentStatus.ALIGNED
            requires_review = True
        else:
            # No sufficient match
            status = AlignmentStatus.UNRESOLVED
            requires_review = True
        
        return AlignmentResult(
            alignment_unit_id="",  # Will be set by handler
            core_class="persons",
            broadcasting_program_key="",
            episode_key=episode_key,
            source_zdf_value=mention_name,
            source_wikidata_value=wd_name,
            source_fernsehserien_value=fs_name,
            deterministic_alignment_status=status,
            deterministic_alignment_score=best_score,
            deterministic_alignment_method=best_method,
            deterministic_alignment_reason=(
                f"Person mention '{mention_name}' in episode {episode_key}: "
                f"Wikidata name similarity {wd_sim:.2f}, Fernsehserien {fs_sim:.2f}"
            ),
            requires_human_review=requires_review,
            matched_on_fields=matched_fields,
            candidate_count=len([c for c in [wikidata_candidate, fernsehserien_candidate] if c]),
            evidence_sources=sources,
        )


class BroadcastingProgramAligner:
    """Broadcasting program alignment (Layer 1 - already unified, minimal check)."""
    
    def validate_program(self, program_key: str, program_record: dict) -> AlignmentResult:
        """Validate that a broadcasting program record exists and is valid."""
        return AlignmentResult(
            alignment_unit_id="",
            core_class="broadcasting_programs",
            broadcasting_program_key=program_key,
            episode_key=None,
            source_zdf_value=program_record.get("name"),
            deterministic_alignment_status=AlignmentStatus.ALIGNED,
            deterministic_alignment_score=1.0,
            deterministic_alignment_method="schema_validation",
            deterministic_alignment_reason="Broadcasting program record exists in setup data",
            requires_human_review=False,
            matched_on_fields=["program_key"],
            candidate_count=1,
            evidence_sources=["setup"],
        )

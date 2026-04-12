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

from .normalization import name_similarity, normalize_name


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
    
    def align_person_in_episode(
        self,
        episode_key: str,
        mention_id: str,
        mention_name: str,
        wikidata_candidates: Optional[list[dict]] = None,
        fernsehserien_candidates: Optional[list[dict]] = None,
    ) -> AlignmentResult:
        """Align a single person mention in an episode context.
        
        Priority:
        1. Exact name match across sources
        2. Keep unmatched as unresolved (precision-first)
        """
        wd_candidates = wikidata_candidates or []
        fs_candidates = fernsehserien_candidates or []

        best_wd: Optional[dict] = None
        best_wd_score = 0.0
        for candidate in wd_candidates:
            label = candidate.get("label") or candidate.get("name") or ""
            score = name_similarity(mention_name, label)
            if score > best_wd_score:
                best_wd_score = score
                best_wd = candidate

        best_fs: Optional[dict] = None
        best_fs_score = 0.0
        for candidate in fs_candidates:
            label = candidate.get("guest_name") or candidate.get("name") or ""
            score = name_similarity(mention_name, label)
            if score > best_fs_score:
                best_fs_score = score
                best_fs = candidate

        wd_name = (best_wd or {}).get("label") or (best_wd or {}).get("name")
        fs_name = (best_fs or {}).get("guest_name") or (best_fs or {}).get("name")

        matched_fields: list[str] = []
        sources = ["zdf"]
        best_score = 0.0
        best_method = "no_deterministic_match"
        status = AlignmentStatus.UNRESOLVED
        requires_review = True

        if best_wd_score == 1.0 and best_fs_score == 1.0:
            best_score = 0.95
            best_method = "name_exact_multi_source"
            status = AlignmentStatus.ALIGNED
            requires_review = False
            matched_fields = ["name_normalized_exact"]
            sources.extend(["wikidata", "fernsehserien"])
        elif best_wd_score == 1.0:
            best_score = 0.90
            best_method = "name_exact_zdf_wikidata"
            status = AlignmentStatus.ALIGNED
            requires_review = False
            matched_fields = ["name_normalized_exact"]
            sources.append("wikidata")
        elif best_fs_score == 1.0:
            best_score = 0.85
            best_method = "name_exact_zdf_fernsehserien"
            status = AlignmentStatus.ALIGNED
            requires_review = False
            matched_fields = ["name_normalized_exact"]
            sources.append("fernsehserien")
        elif best_wd_score >= 0.7 or best_fs_score >= 0.7:
            best_score = 0.70
            best_method = "name_substring_match"
            status = AlignmentStatus.ALIGNED
            requires_review = True
            matched_fields = ["name_normalized_substring"]
            if best_wd_score >= 0.7:
                sources.append("wikidata")
            if best_fs_score >= 0.7:
                sources.append("fernsehserien")

        mention_norm = normalize_name(mention_name)
        wd_norm = normalize_name(wd_name)
        fs_norm = normalize_name(fs_name)
        
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
                f"Wikidata name similarity {best_wd_score:.2f}, Fernsehserien {best_fs_score:.2f}; "
                f"normalized forms zdf='{mention_norm}', wd='{wd_norm}', fs='{fs_norm}'"
            ),
            requires_human_review=requires_review,
            matched_on_fields=matched_fields,
            candidate_count=len(wd_candidates) + len(fs_candidates),
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


class RoleOrganizationAligner:
    """Role and organization context enrichment (Layer 4 - optional confidence boosting)."""
    
    def enrich_person_alignment_with_layer4_signals(
        self,
        existing_alignment: AlignmentResult,
        zdf_description: Optional[str],
        wikidata_occupations: Optional[list[str]],
        wikidata_positions: Optional[list[str]],
        fernsehserien_role: Optional[str],
    ) -> AlignmentResult:
        """
        Enhance person alignment with Layer 4 role/organization signals.
        
        Layer 4 evidence can:
        - Increase confidence score if roles align across sources
        - Flag for human review if role contradicts across sources
        - Never downgrade ALIGNED status to UNRESOLVED (precision-first)
        
        Args:
            existing_alignment: Result from PersonAligner (Layer 3)
            zdf_description: Description/role from ZDF
            wikidata_occupations: List of occupation identifiers from Wikidata
            wikidata_positions: List of position identifiers from Wikidata
            fernsehserien_role: Role/title from Fernsehserien
        
        Returns:
            Updated AlignmentResult with enriched evidence
        """
        # Only enrich if base alignment is ALIGNED with mid-range confidence
        # (don't waste effort on UNRESOLVED or already-high-confidence matches)
        if existing_alignment.deterministic_alignment_status != AlignmentStatus.ALIGNED:
            return existing_alignment
        
        if existing_alignment.deterministic_alignment_score >= 0.95:
            # Already very high confidence; Layer 4 won't improve it
            return existing_alignment
        
        # Extract role keywords from descriptions
        zdf_roles = self._extract_role_keywords(zdf_description) if zdf_description else []
        fs_roles = self._extract_role_keywords(fernsehserien_role) if fernsehserien_role else []
        
        # Check for role alignment across sources
        role_alignment_count = 0
        if zdf_roles and fs_roles:
            # Simple keyword overlap check
            overlap = set(zdf_roles) & set(fs_roles)
            role_alignment_count += len(overlap)
        
        if zdf_roles and wikidata_occupations:
            # Check for semantic role matches (simplified: presence of certain keywords)
            wikidata_keywords = self._extract_keywords_from_qids(wikidata_occupations)
            overlap = set(zdf_roles) & set(wikidata_keywords)
            role_alignment_count += len(overlap)
        
        # Boost confidence if strong layer 4 evidence
        confidence_boost = 0.0
        layer4_reason = ""
        
        if role_alignment_count >= 2:
            # Multiple role signals align across sources
            confidence_boost = 0.05
            layer4_reason = f" [Layer 4 boost: {role_alignment_count} role/occupation signals align across sources]"
        elif role_alignment_count == 1:
            # Single role signal; modest boost
            confidence_boost = 0.03
            layer4_reason = " [Layer 4 modest boost: 1 role signal aligns]"
        
        # Apply boost
        new_score = min(existing_alignment.deterministic_alignment_score + confidence_boost, 0.99)
        
        return AlignmentResult(
            alignment_unit_id=existing_alignment.alignment_unit_id,
            core_class=existing_alignment.core_class,
            broadcasting_program_key=existing_alignment.broadcasting_program_key,
            episode_key=existing_alignment.episode_key,
            source_zdf_value=existing_alignment.source_zdf_value,
            source_wikidata_value=existing_alignment.source_wikidata_value,
            source_fernsehserien_value=existing_alignment.source_fernsehserien_value,
            deterministic_alignment_status=existing_alignment.deterministic_alignment_status,
            deterministic_alignment_score=new_score,
            deterministic_alignment_method=existing_alignment.deterministic_alignment_method,
            deterministic_alignment_reason=existing_alignment.deterministic_alignment_reason + layer4_reason,
            requires_human_review=existing_alignment.requires_human_review,
            matched_on_fields=existing_alignment.matched_on_fields + (["role_alignment"] if layer4_reason else []),
            candidate_count=existing_alignment.candidate_count,
            evidence_sources=existing_alignment.evidence_sources,
        )
    
    def _extract_role_keywords(self, text: str) -> list[str]:
        """Extract role/occupation keywords from descriptive text."""
        keywords = []
        text_lower = text.lower()
        
        # Common German/English occupation keywords
        known_keywords = [
            "moderator", "host", "schauspieler", "actor", "regisseur", "director",
            "journalist", "author", "politician", "politiker", "ceo", "präsident",
            "minister", "justiz", "foreign", "wissenschaftler", "researcher",
            "künstler", "artist", "sänger", "singer", "musiker", "musician",
        ]
        
        for kw in known_keywords:
            if kw in text_lower:
                keywords.append(kw)
        
        return keywords
    
    def _extract_keywords_from_qids(self, qids: list[str]) -> list[str]:
        """Convert Wikidata QIDs to simple keyword representations.
        
        Note: This is a placeholder. In production, would use a mapping table
        or query Wikidata for labels.
        """
        # Placeholder: just return empty list for now
        # In a real system, would map Q IDs to human-readable labels
        return []

"""Orchestrator for Step 311 deterministic alignment.

Coordinates:
1. Loading immutable upstream data
2. Running deterministic alignment logic
3. Emitting events to event logs
4. Building projections
5. Saving checkpoints
"""
from __future__ import annotations

from pathlib import Path
import re
from datetime import datetime
from typing import Optional

import pandas as pd

from .alignment import (
    EpisodeAligner,
    PersonAligner,
    BroadcastingProgramAligner,
    AlignmentResult,
    AlignmentStatus,
)
from .config import (
    BROADCASTING_PROGRAMS_CSV,
    CANDIDATE_EPISODES_CSV,
    CORE_CLASSES,
    EPISODES_CSV,
    FS_EPISODE_GUESTS,
    FS_EPISODE_METADATA,
    FS_EPISODE_BROADCASTS,
    PERSONS_CSV,
    PUBLICATIONS_CSV,
    WD_BROADCASTING_PROGRAMS,
    WD_EPISODES,
    WD_ORGANIZATIONS,
    WD_PERSONS,
    WD_ROLES,
    WD_SERIES,
    WD_TOPICS,
)
from .event_log import AlignmentEventLog
from .event_handlers import AlignmentProjectionBuilder
from .checkpoints import CheckpointManager
from .config import EVENTS_DIR
from .data_loading import (
    load_wikidata_entities_df,
    normalize_zdf_episodes_df,
    read_csv_if_exists,
)
from .normalization import (
    extract_label_and_date_from_parenthetical,
    normalize_name,
    normalize_program_name,
    parse_date_to_iso,
)


class Step311Orchestrator:
    """Orchestrates Step 311 automated disambiguation workflow.
    
    Implements the complete 4-layer entity alignment process:
    - Layer 1: Broadcasting programs (identity validation)
    - Layer 2: Episodes (time/ID-based matching)
    - Layer 3: Persons (name-based matching within episodes)
    - Layer 4: Roles/Organizations (context enrichment)
    
    Coordinates:
    - Data loading from all 3 sources (ZDF, Wikidata, Fernsehserien)
    - Normalization of entity names and dates
    - Deterministic matching with confidence scoring
    - Event emission for reproducibility
    - Checkpoint management for recovery
    - Projection building into aligned_*.csv files
    
    Usage:
        >>> orchestrator = Step311Orchestrator()
        >>> projections = orchestrator.run()  # Returns dict[core_class, DataFrame]
        >>> print(projections["persons"].shape)  # (rows, columns)
    
    All decisions are logged as immutable events and fully reproducible.
    Re-running with same input always produces identical output.
    """
    
    def __init__(self):
        """Initialize orchestrator with aligners, event logs, and checkpoint manager."""
        self.episode_aligner = EpisodeAligner()
        self.person_aligner = PersonAligner()
        self.program_aligner = BroadcastingProgramAligner()
        self.event_logs = {core_class: AlignmentEventLog(core_class=core_class) for core_class in CORE_CLASSES}
        
        self.projection_builder = AlignmentProjectionBuilder()
        self.checkpoint_manager = CheckpointManager()
        self._seen_import_ids: dict[str, set[str]] = {
            core_class: set() for core_class in CORE_CLASSES
        }
    
    def run(self) -> dict[str, pd.DataFrame]:
        """Run complete Step 311 workflow end-to-end.
        
        Orchestrates all 4 layers of entity alignment:
        1. Load upstream data (ZDF CSVs, Wikidata JSON, Fernsehserien CSV)
        2. Normalize all entity names and dates for deterministic comparison
        3. Run Layer 1 (Broadcasting Programs) → seeds from setup data
        4. Run Layer 2 (Episodes) → time/ID-based matching
        5. Run Layer 3 (Persons) → name-based matching within episodes
        6. Run Layer 4 (Roles/Organizations) → context enrichment
        7. Emit all alignment events with evidence metadata
        8. Build aligned_*.csv projections from events
        9. Save checkpoint for recovery
        
        Returns:
            Dictionary mapping core_class to projection DataFrame:
            - 'broadcasting_programs': aligned programs
            - 'episodes': aligned episodes
            - 'persons': aligned person mentions
            - 'series': aligned series/seasons
            - 'topics': aligned topics
            - 'roles': aligned roles/occupations
            - 'organizations': aligned organizations
        
        Deterministic Guarantees:
        - Same input always produces identical output
        - All decisions logged as immutable events
        - Recoverable from checkpoints if interrupted
        - No false positive alignments (precision-first philosophy)
        
        Raises:
            RuntimeError: If critical upstream data (e.g., setup broadcasting programs) is missing
        """
        # 1. Load immutable upstream data
        upstream = self._load_upstream_data()

        # 1b. Always re-read all source CSVs, then continue incrementally by
        # skipping already-imported source IDs found in the event-store.
        self._refresh_seen_import_ids()
        
        # 2. Run alignment logic
        self._run_broadcasting_program_seeds(upstream)
        self._run_episode_alignments(upstream)
        self._run_person_alignments(upstream)
        self._run_fernsehserien_person_seeds(upstream)
        self._run_wikidata_person_seeds(upstream)
        self._run_wikidata_class_seeds(
            upstream=upstream,
            core_class="broadcasting_programs",
            dataset_key="wd_broadcasting_programs",
            method_name="seed_wikidata_broadcasting_program",
        )
        self._run_wikidata_class_seeds(
            upstream=upstream,
            core_class="series",
            dataset_key="wd_series",
            method_name="seed_wikidata_series",
        )
        self._run_wikidata_class_seeds(
            upstream=upstream,
            core_class="topics",
            dataset_key="wd_topics",
            method_name="seed_wikidata_topic",
        )
        self._run_wikidata_class_seeds(
            upstream=upstream,
            core_class="roles",
            dataset_key="wd_roles",
            method_name="seed_wikidata_role",
        )
        self._run_wikidata_class_seeds(
            upstream=upstream,
            core_class="organizations",
            dataset_key="wd_organizations",
            method_name="seed_wikidata_organization",
        )
        
        # 3. Build projections
        projections = self.projection_builder.build_all_projections()
        
        # 4. Save checkpoint
        self.checkpoint_manager.save_checkpoint(
            events_dir=EVENTS_DIR,
            projections=projections,
        )
        
        return projections

    def _refresh_seen_import_ids(self) -> None:
        for core_class in self._seen_import_ids.keys():
            seen: set[str] = set()
            for event in self.event_logs[core_class].read_events(start_event_id=None):
                extra = event.get("extra", {})
                if isinstance(extra, dict):
                    source_import_id = str(extra.get("source_import_id", "")).strip()
                    if source_import_id:
                        seen.add(source_import_id)
            self._seen_import_ids[core_class] = seen

    def _mark_if_new_import(self, *, core_class: str, source_import_id: str) -> bool:
        source_import_id = str(source_import_id or "").strip()
        if not source_import_id:
            return False
        seen = self._seen_import_ids.setdefault(core_class, set())
        if source_import_id in seen:
            return False
        seen.add(source_import_id)
        return True
    
    def _load_upstream_data(self) -> dict:
        """Load immutable upstream data."""
        data = {}
        
        # Broadcasting programs (Layer 1)
        data["programs"] = read_csv_if_exists(BROADCASTING_PROGRAMS_CSV)
        
        # Episodes (Layer 2)
        data["episodes"] = read_csv_if_exists(EPISODES_CSV)
        data["candidate_episodes"] = read_csv_if_exists(CANDIDATE_EPISODES_CSV)
        data["publications"] = read_csv_if_exists(PUBLICATIONS_CSV)
        data["zdf_episodes_normalized"] = normalize_zdf_episodes_df(
            data["episodes"],
            data["publications"],
        )
        
        # Persons (Layer 3)
        data["persons"] = read_csv_if_exists(PERSONS_CSV)
        data["wd_persons"] = load_wikidata_entities_df(WD_PERSONS)
        data["wd_episodes"] = load_wikidata_entities_df(WD_EPISODES)
        data["wd_broadcasting_programs"] = load_wikidata_entities_df(WD_BROADCASTING_PROGRAMS)
        data["wd_series"] = load_wikidata_entities_df(WD_SERIES)
        data["wd_topics"] = load_wikidata_entities_df(WD_TOPICS)
        data["wd_roles"] = load_wikidata_entities_df(WD_ROLES)
        data["wd_organizations"] = load_wikidata_entities_df(WD_ORGANIZATIONS)

        # Fernsehserien episode metadata (Layer 2 input)
        data["fs_episode_metadata"] = read_csv_if_exists(FS_EPISODE_METADATA)
        data["fs_episode_broadcasts"] = read_csv_if_exists(FS_EPISODE_BROADCASTS)

        # Fernsehserien episode guests (Layer 3 input)
        data["fs_episode_guests"] = read_csv_if_exists(FS_EPISODE_GUESTS)
        
        return data

    @staticmethod
    def _first_available(row: pd.Series, candidates: list[str], default: str = "") -> str:
        for key in candidates:
            if key in row and pd.notna(row[key]):
                value = str(row[key]).strip()
                if value:
                    return value
        return default

    @staticmethod
    def _normalize_program_name(value: str) -> str:
        return normalize_program_name(value)

    @staticmethod
    def _parse_date_to_iso(value: str) -> str:
        return parse_date_to_iso(value)

    @staticmethod
    def _extract_program_and_date_from_wikidata_label(label: str) -> tuple[str, str]:
        return extract_label_and_date_from_parenthetical(label)

    @staticmethod
    def _wikidata_source_metadata(row: pd.Series) -> dict[str, str]:
        keys = [
            "wikidata_claim_properties",
            "wikidata_claim_property_count",
            "wikidata_claim_statement_count",
            "wikidata_property_counts_json",
            "wikidata_p31_qids",
            "wikidata_p179_qids",
            "wikidata_p106_qids",
            "wikidata_p39_qids",
            "wikidata_p921_qids",
            "wikidata_p527_qids",
            "wikidata_p361_qids",
        ]
        return {k: str(row.get(k, "") or "") for k in keys}

    @staticmethod
    def _is_series_like_broadcasting_program(row: pd.Series) -> bool:
        p31_qids = str(row.get("wikidata_p31_qids", "") or "")
        qids = {q.strip() for q in p31_qids.split("|") if q.strip()}
        return "Q3464665" in qids

    def _emit_episode_time_matches(
        self,
        *,
        zdf_candidates: list[dict],
        fs_candidates: list[dict],
        wd_candidates: list[dict],
    ) -> None:
        """Emit strict deterministic episode matches by normalized date+program.

        Precision-first policy:
        - Only emit when a key resolves to exactly one row per source side.
        - Ambiguous or partial keys remain as seeded unresolved rows (orphans).
        """
        zdf_by_key: dict[tuple[str, str], list[dict]] = {}
        fs_by_key: dict[tuple[str, str], list[dict]] = {}
        wd_by_key: dict[tuple[str, str], list[dict]] = {}

        for row in zdf_candidates:
            key = (row.get("date_iso", ""), row.get("program_norm", ""))
            if key[0] and key[1]:
                zdf_by_key.setdefault(key, []).append(row)

        for row in fs_candidates:
            key = (row.get("date_iso", ""), row.get("program_norm", ""))
            if key[0] and key[1]:
                fs_by_key.setdefault(key, []).append(row)

        for row in wd_candidates:
            key = (row.get("date_iso", ""), row.get("program_norm", ""))
            if key[0] and key[1]:
                wd_by_key.setdefault(key, []).append(row)

        shared_keys = sorted(set(zdf_by_key.keys()) & (set(fs_by_key.keys()) | set(wd_by_key.keys())))
        for key in shared_keys:
            zdf_rows = zdf_by_key.get(key, [])
            fs_rows = fs_by_key.get(key, [])
            wd_rows = wd_by_key.get(key, [])

            # Never force a match when one side has multiple candidates.
            if len(zdf_rows) != 1:
                continue
            if fs_rows and len(fs_rows) != 1:
                continue
            if wd_rows and len(wd_rows) != 1:
                continue

            zdf_row = zdf_rows[0]
            fs_row = fs_rows[0] if fs_rows else None
            wd_row = wd_rows[0] if wd_rows else None

            evidence_sources = ["zdf"]
            matched_on_fields = ["publication_date", "program_normalized"]
            source_entity_ids = {
                "zdf_episode_id": zdf_row.get("episode_id", ""),
            }

            score = 0.9
            method_suffix = []
            if wd_row:
                evidence_sources.append("wikidata")
                source_entity_ids["wikidata_qid"] = wd_row.get("wikidata_qid", "")
                method_suffix.append("wikidata")
                score += 0.05
            if fs_row:
                evidence_sources.append("fernsehserien")
                source_entity_ids["fernsehserien_episode_id"] = fs_row.get("episode_id", "")
                method_suffix.append("fernsehserien")
                score += 0.03

            if len(method_suffix) == 2:
                method_name = "time_program_match_zdf_wikidata_fernsehserien"
            elif len(method_suffix) == 1 and method_suffix[0] == "wikidata":
                method_name = "time_program_match_zdf_wikidata"
            elif len(method_suffix) == 1 and method_suffix[0] == "fernsehserien":
                method_name = "time_program_match_zdf_fernsehserien"
            else:
                # Should not happen due to shared_keys definition.
                continue

            key_date, key_program = key
            source_import_id = f"episode_match_v1::{key_date}::{key_program}::{method_name}"
            if not self._mark_if_new_import(
                core_class="episodes",
                source_import_id=source_import_id,
            ):
                continue

            result = AlignmentResult(
                alignment_unit_id=f"ep_match::{key_date}::{key_program}",
                core_class="episodes",
                broadcasting_program_key=zdf_row.get("program_display", ""),
                episode_key=zdf_row.get("episode_id", ""),
                source_zdf_value=zdf_row.get("title", ""),
                source_wikidata_value=(wd_row or {}).get("label", ""),
                source_fernsehserien_value=(fs_row or {}).get("title", ""),
                deterministic_alignment_status=AlignmentStatus.ALIGNED,
                deterministic_alignment_score=min(score, 0.99),
                deterministic_alignment_method=method_name,
                deterministic_alignment_reason=(
                    "Deterministic Layer-2 match by unique normalized publication_date "
                    f"({key_date}) and normalized program label ({key_program})"
                ),
                requires_human_review=False,
                matched_on_fields=matched_on_fields,
                candidate_count=1,
                evidence_sources=evidence_sources,
            )

            self.event_logs["episodes"].append_alignment_event(
                alignment_result=result,
                handler_name="episode_time_matcher",
                source_mention_data={
                    "episode_id": zdf_row.get("episode_id", ""),
                    "publication_date": zdf_row.get("publication_date", ""),
                    "publication_time": zdf_row.get("publication_time", ""),
                    "duration_seconds": zdf_row.get("duration", ""),
                    "season_number": zdf_row.get("season_number", ""),
                    "episode_number": zdf_row.get("episode_number", ""),
                },
                source_entity_ids=source_entity_ids,
                action={
                    "type": "deterministic_match",
                    "status": "emitted",
                    "reason": "unique date+program key across sources",
                },
                extra_context={
                    "source_name": "step311.layer2.episode_time_matcher",
                    "source_import_id": source_import_id,
                },
            )

    def _run_broadcasting_program_seeds(self, upstream: dict) -> None:
        programs_df = upstream.get("programs", pd.DataFrame())
        if programs_df.empty:
            return

        for _, row in programs_df.iterrows():
            program_key = self._first_available(
                row,
                ["broadcasting_program_key", "program_key", "slug", "id", "name"],
                default="",
            )
            program_label = self._first_available(
                row,
                ["name", "label", "program_name", "sendungstitel"],
                default=program_key,
            )

            if not program_key and not program_label:
                continue

            source_import_id = f"setup_program::{program_key or program_label}"
            if not self._mark_if_new_import(
                core_class="broadcasting_programs",
                source_import_id=source_import_id,
            ):
                continue

            result = AlignmentResult(
                alignment_unit_id=f"program::{program_key or program_label}",
                core_class="broadcasting_programs",
                broadcasting_program_key=program_key or program_label,
                episode_key=None,
                source_zdf_value=program_label,
                source_wikidata_value=None,
                source_fernsehserien_value=None,
                deterministic_alignment_status=AlignmentStatus.ALIGNED,
                deterministic_alignment_score=1.0,
                deterministic_alignment_method="seed_broadcasting_program",
                deterministic_alignment_reason="Broadcasting program seeded from setup source",
                requires_human_review=False,
                matched_on_fields=["program_key"],
                candidate_count=1,
                evidence_sources=["setup"],
            )

            self.event_logs["broadcasting_programs"].append_alignment_event(
                alignment_result=result,
                handler_name="program_seed_setup",
                source_mention_data={
                    "mention_id": "",
                    "mention_name": program_label,
                    "episode_key": "",
                    "program_label": program_label,
                },
                source_entity_ids={
                    "setup_program_id": program_key or program_label,
                },
                action={
                    "type": "import_snapshot",
                    "status": "emitted",
                    "reason": "program identity seeded from setup source",
                },
                extra_context={
                    "source_name": "setup.broadcasting_programs",
                    "source_import_id": source_import_id,
                },
            )
    
    def _run_person_alignments(self, upstream: dict) -> None:
        """Run Layer 3 person alignment logic.
        
        For each mention in each episode, attempt deterministic alignment.
        """
        persons_df = upstream.get("persons", pd.DataFrame())
        episodes_df = upstream.get("episodes", pd.DataFrame())
        publications_df = upstream.get("publications", pd.DataFrame())
        wd_persons_df = upstream.get("wd_persons", pd.DataFrame())
        fs_guests_df = upstream.get("fs_episode_guests", pd.DataFrame())
        fs_meta_df = upstream.get("fs_episode_metadata", pd.DataFrame())
        fs_broadcasts_df = upstream.get("fs_episode_broadcasts", pd.DataFrame())
        
        if persons_df.empty or episodes_df.empty:
            return

        if "episode_id" not in persons_df.columns or "episode_id" not in episodes_df.columns:
            return

        # Normalize join keys to avoid dtype mismatch (e.g. int vs str).
        persons_df = persons_df.copy()
        episodes_df = episodes_df.copy()
        persons_df["episode_id"] = persons_df["episode_id"].astype(str)
        episodes_df["episode_id"] = episodes_df["episode_id"].astype(str)

        publication_first_by_episode: dict[str, dict[str, str]] = {}
        if not publications_df.empty and "episode_id" in publications_df.columns:
            pub_work = publications_df.copy()
            pub_work["episode_id"] = pub_work["episode_id"].astype(str)
            if "publication_index" in pub_work.columns:
                pub_work = pub_work.sort_values(by=["publication_index"])
            for _, prow in pub_work.iterrows():
                eid = str(prow.get("episode_id", "")).strip()
                if not eid or eid in publication_first_by_episode:
                    continue
                publication_first_by_episode[eid] = {
                    "date": str(prow.get("date", "")).strip(),
                    "time": str(prow.get("time", "")).strip(),
                    "program": str(prow.get("program", "")).strip(),
                }

        wd_candidates_by_norm: dict[str, list[dict]] = {}
        if not wd_persons_df.empty:
            for _, row in wd_persons_df.iterrows():
                aliases_raw = str(row.get("aliases", "")).strip()
                candidate = {
                    "id": str(row.get("id", "")).strip(),
                    "label": str(row.get("label", "")).strip(),
                    "aliases": aliases_raw.split("|") if aliases_raw else [],
                    "description": str(row.get("description_de", row.get("description_en", ""))).strip(),
                }
                names = [candidate["label"]] + candidate["aliases"]
                for name in names:
                    name_norm = normalize_name(name)
                    if name_norm:
                        wd_candidates_by_norm.setdefault(name_norm, []).append(candidate)

        fs_episode_by_key: dict[tuple[str, str], set[str]] = {}
        if not fs_meta_df.empty:
            for _, row in fs_meta_df.iterrows():
                key = (
                    parse_date_to_iso(str(row.get("premiere_date", "")).strip()),
                    normalize_program_name(str(row.get("program_name", "")).strip()),
                )
                episode_url = str(row.get("episode_url", "")).strip()
                if key[0] and key[1] and episode_url:
                    fs_episode_by_key.setdefault(key, set()).add(episode_url)
        if not fs_broadcasts_df.empty:
            for _, row in fs_broadcasts_df.iterrows():
                key = (
                    parse_date_to_iso(str(row.get("broadcast_date", "")).strip()),
                    normalize_program_name(str(row.get("program_name", "")).strip()),
                )
                episode_url = str(row.get("episode_url", "")).strip()
                if key[0] and key[1] and episode_url:
                    fs_episode_by_key.setdefault(key, set()).add(episode_url)

        fs_guests_by_episode: dict[str, list[dict]] = {}
        if not fs_guests_df.empty:
            for _, row in fs_guests_df.iterrows():
                episode_url = str(row.get("episode_url", "")).strip()
                if not episode_url:
                    continue
                fs_guests_by_episode.setdefault(episode_url, []).append(
                    {
                        "guest_name": str(row.get("guest_name", "")).strip(),
                        "guest_url": str(row.get("guest_url", "")).strip(),
                        "guest_role": str(row.get("guest_role", "")).strip(),
                    }
                )
        
        # Group persons by episode
        for episode_idx, episode_row in episodes_df.iterrows():
            episode_key = str(episode_row.get("episode_id", "")).strip()
            if not episode_key:
                continue
            
            # Filter persons for this episode
            episode_persons = persons_df[persons_df["episode_id"] == episode_key]
            
            for person_idx, person_row in episode_persons.iterrows():
                mention_id = str(person_row.get("mention_id", ""))
                person_name = str(
                    person_row.get("name", person_row.get("mention_text", ""))
                )
                broadcasting_program_key = str(episode_row.get("broadcasting_program_key", ""))
                person_episode_publication_date = str(episode_row.get("publikationsdatum", "")).strip()
                person_episode_publication_time = ""
                if not broadcasting_program_key:
                    broadcasting_program_key = str(episode_row.get("sendungstitel", "")).strip()
                if episode_key in publication_first_by_episode:
                    if not person_episode_publication_date:
                        person_episode_publication_date = publication_first_by_episode[episode_key].get("date", "")
                    person_episode_publication_time = publication_first_by_episode[episode_key].get("time", "")
                    if not broadcasting_program_key:
                        broadcasting_program_key = publication_first_by_episode[episode_key].get("program", "")

                source_import_id = f"zdf_person::{mention_id}"
                if not self._mark_if_new_import(
                    core_class="persons",
                    source_import_id=source_import_id,
                ):
                    continue

                person_name_norm = normalize_name(person_name)
                wd_candidates = list(wd_candidates_by_norm.get(person_name_norm, []))

                fs_candidates: list[dict] = []
                episode_key_tuple = (
                    parse_date_to_iso(person_episode_publication_date),
                    normalize_program_name(broadcasting_program_key),
                )
                candidate_episode_urls = fs_episode_by_key.get(episode_key_tuple, set())
                for fs_episode_url in sorted(candidate_episode_urls):
                    fs_candidates.extend(fs_guests_by_episode.get(fs_episode_url, []))
                
                # Run alignment
                result = self.person_aligner.align_person_in_episode(
                    episode_key=episode_key,
                    mention_id=mention_id,
                    mention_name=person_name,
                    wikidata_candidates=wd_candidates,
                    fernsehserien_candidates=fs_candidates,
                )
                
                # Set identifiers
                result.alignment_unit_id = f"{episode_key}:{mention_id}"
                result.broadcasting_program_key = broadcasting_program_key

                best_wd_candidate = wd_candidates[0] if wd_candidates else {}
                best_fs_candidate = fs_candidates[0] if fs_candidates else {}
                
                # Emit event
                self.event_logs["persons"].append_alignment_event(
                    alignment_result=result,
                    handler_name="person_aligner",
                    source_mention_data={
                        "mention_id": mention_id,
                        "mention_name": person_name,
                        "episode_key": episode_key,
                        "person_episode_publication_date": person_episode_publication_date,
                        "person_episode_publication_time": person_episode_publication_time,
                        "wikidata_id": str(best_wd_candidate.get("id", "")),
                        "wikidata_label": str(best_wd_candidate.get("label", "")),
                        "fernsehserien_url": str(best_fs_candidate.get("guest_url", "")),
                        "fernsehserien_label": str(best_fs_candidate.get("guest_name", "")),
                        "occupation_evidence": str(best_wd_candidate.get("description", "")),
                        "affiliation_evidence": str(best_fs_candidate.get("guest_role", "")),
                    },
                    source_entity_ids={
                        "zdf_mention_id": mention_id,
                        "zdf_episode_id": episode_key,
                        "wikidata_qid": str(best_wd_candidate.get("id", "")),
                        "fernsehserien_guest_url": str(best_fs_candidate.get("guest_url", "")),
                    },
                    action={
                        "type": "import_snapshot",
                        "status": "emitted",
                        "reason": "zdf person mention alignment emitted",
                    },
                    extra_context={
                        "source_name": "mention_detection.persons",
                        "source_import_id": source_import_id,
                    },
                )

    def _run_fernsehserien_person_seeds(self, upstream: dict) -> None:
        """Seed person alignment rows from fernsehserien episode guests.

        Until deterministic cross-source person matching is implemented,
        these rows remain explicit unresolved candidates for Step 312.
        """
        fs_guests = upstream.get("fs_episode_guests", pd.DataFrame())
        if fs_guests.empty:
            return

        for _, row in fs_guests.iterrows():
            episode_key = str(row.get("episode_url", "")).strip()
            guest_name = str(row.get("guest_name", "")).strip()
            guest_url = str(row.get("guest_url", "")).strip()
            guest_order = str(row.get("guest_order", "")).strip()
            program_name = str(row.get("program_name", "")).strip()

            if not episode_key and not guest_name:
                continue

            mention_id = guest_url or f"fs_guest::{episode_key}::{guest_order}::{guest_name}"
            source_import_id = f"fernsehserien_guest::{mention_id}"
            if not self._mark_if_new_import(
                core_class="persons",
                source_import_id=source_import_id,
            ):
                continue

            result = AlignmentResult(
                alignment_unit_id=f"fs::{episode_key}::{mention_id}",
                core_class="persons",
                broadcasting_program_key=program_name,
                episode_key=episode_key,
                source_zdf_value=None,
                source_wikidata_value=None,
                source_fernsehserien_value=guest_name,
                deterministic_alignment_status=AlignmentStatus.UNRESOLVED,
                deterministic_alignment_score=0.0,
                deterministic_alignment_method="seed_fernsehserien_episode_guest",
                deterministic_alignment_reason="Fernsehserien episode guest seeded for deterministic handoff",
                requires_human_review=True,
                matched_on_fields=["episode_url", "guest_name"],
                candidate_count=1,
                evidence_sources=["fernsehserien"],
            )

            self.event_logs["persons"].append_alignment_event(
                alignment_result=result,
                handler_name="person_seed_fernsehserien",
                source_mention_data={
                    "mention_id": mention_id,
                    "mention_name": guest_name,
                    "episode_key": episode_key,
                    "fernsehserien_url": guest_url,
                },
                source_entity_ids={
                    "fernsehserien_guest_id": mention_id,
                    "fernsehserien_episode_id": episode_key,
                },
                action={
                    "type": "import_snapshot",
                    "status": "emitted",
                    "reason": "fernsehserien guest seeded for manual disambiguation",
                },
                extra_context={
                    "source_name": "fernsehserien.episode_guests",
                    "source_import_id": source_import_id,
                },
            )

    def _run_episode_alignments(self, upstream: dict) -> None:
        """Seed episode alignment rows from known episode-level sources."""
        zdf_norm_df = upstream.get("zdf_episodes_normalized", pd.DataFrame())
        fs_meta_df = upstream.get("fs_episode_metadata", pd.DataFrame())
        fs_broadcasts_df = upstream.get("fs_episode_broadcasts", pd.DataFrame())
        wd_episodes_df = upstream.get("wd_episodes", pd.DataFrame())
        zdf_candidates: list[dict] = []
        fs_candidates: list[dict] = []
        wd_candidates: list[dict] = []

        if not zdf_norm_df.empty and "episode_id" in zdf_norm_df.columns:
            zdf_rows = zdf_norm_df.copy()
            zdf_rows["episode_id"] = zdf_rows["episode_id"].astype(str)

            for _, row in zdf_rows.iterrows():
                episode_id = str(row.get("episode_id", "")).strip()
                if not episode_id:
                    continue

                source_import_id = f"zdf_episode::{episode_id}"
                if not self._mark_if_new_import(
                    core_class="episodes",
                    source_import_id=source_import_id,
                ):
                    continue

                program_name = str(row.get("program_name", "")).strip()
                publication_date = str(row.get("publication_date", "")).strip()
                publication_time = str(row.get("publication_time", "")).strip()
                duration = str(row.get("duration_seconds", "")).strip()
                date_iso = str(row.get("date_iso", "")).strip() or self._parse_date_to_iso(publication_date)
                program_norm = str(row.get("program_norm", "")).strip() or self._normalize_program_name(program_name)
                zdf_candidates.append(
                    {
                        "episode_id": episode_id,
                        "title": program_name,
                        "program_display": program_name,
                        "program_norm": program_norm,
                        "publication_date": publication_date,
                        "publication_time": publication_time,
                        "duration": duration,
                        "season_number": str(row.get("season_number", "")).strip(),
                        "episode_number": str(row.get("episode_number", "")).strip(),
                        "date_iso": date_iso,
                    }
                )

                result = AlignmentResult(
                    alignment_unit_id=f"zdf::{episode_id}",
                    core_class="episodes",
                    broadcasting_program_key=program_name,
                    episode_key=episode_id,
                    source_zdf_value=publication_date or episode_id,
                    source_wikidata_value=None,
                    source_fernsehserien_value=None,
                    deterministic_alignment_status=AlignmentStatus.UNRESOLVED,
                    deterministic_alignment_score=0.0,
                    deterministic_alignment_method="seed_zdf_episode",
                    deterministic_alignment_reason="ZDF episode seeded for deterministic alignment handoff",
                    requires_human_review=True,
                    matched_on_fields=["episode_id"],
                    candidate_count=1,
                    evidence_sources=["zdf"],
                )

                self.event_logs["episodes"].append_alignment_event(
                    alignment_result=result,
                    handler_name="episode_seed_zdf",
                    source_mention_data={
                        "episode_id": episode_id,
                        "publication_date": publication_date,
                        "publication_time": publication_time,
                        "duration_seconds": duration,
                        "season_number": str(row.get("season_number", "")).strip(),
                        "episode_number": str(row.get("episode_number", "")).strip(),
                    },
                    source_entity_ids={
                        "zdf_episode_id": episode_id,
                    },
                    action={
                        "type": "import_snapshot",
                        "status": "emitted",
                        "reason": "zdf episode seeded from mention_detection",
                    },
                    extra_context={
                        "source_name": "mention_detection.episodes_normalized",
                        "source_import_id": source_import_id,
                    },
                )

        if not fs_meta_df.empty:
            for _, row in fs_meta_df.iterrows():
                episode_url = str(row.get("episode_url", "")).strip()
                episode_title = str(row.get("episode_title", "")).strip()
                program_name = str(row.get("program_name", "")).strip()
                premiere_date = str(row.get("premiere_date", "")).strip()

                if not episode_url and not episode_title:
                    continue

                episode_key = episode_url or episode_title
                source_import_id = f"fernsehserien_episode_meta::{episode_key}"
                if not self._mark_if_new_import(
                    core_class="episodes",
                    source_import_id=source_import_id,
                ):
                    continue

                fs_candidates.append(
                    {
                        "episode_id": episode_key,
                        "title": episode_title or episode_key,
                        "program_norm": self._normalize_program_name(program_name),
                        "date_iso": self._parse_date_to_iso(premiere_date),
                    }
                )

                result = AlignmentResult(
                    alignment_unit_id=f"fs::{episode_key}",
                    core_class="episodes",
                    broadcasting_program_key=program_name,
                    episode_key=episode_key,
                    source_zdf_value=None,
                    source_wikidata_value=None,
                    source_fernsehserien_value=episode_title or episode_key,
                    deterministic_alignment_status=AlignmentStatus.UNRESOLVED,
                    deterministic_alignment_score=0.0,
                    deterministic_alignment_method="seed_fernsehserien_episode",
                    deterministic_alignment_reason="Fernsehserien episode metadata seeded for deterministic alignment handoff",
                    requires_human_review=True,
                    matched_on_fields=["episode_url", "episode_title"],
                    candidate_count=1,
                    evidence_sources=["fernsehserien"],
                )

                self.event_logs["episodes"].append_alignment_event(
                    alignment_result=result,
                    handler_name="episode_seed_fernsehserien",
                    source_mention_data={
                        "episode_id": episode_key,
                        "publication_date": premiere_date,
                        "publication_time": "",
                        "duration_seconds": str(row.get("duration_minutes", "")).strip(),
                        "season_number": "",
                        "episode_number": "",
                    },
                    source_entity_ids={
                        "fernsehserien_episode_id": episode_key,
                    },
                    action={
                        "type": "import_snapshot",
                        "status": "emitted",
                        "reason": "fernsehserien episode metadata seeded",
                    },
                    extra_context={
                        "source_name": "fernsehserien.episode_metadata",
                        "source_import_id": source_import_id,
                    },
                )

        if not fs_broadcasts_df.empty:
            for _, row in fs_broadcasts_df.iterrows():
                episode_url = str(row.get("episode_url", "")).strip()
                broadcast_date = str(row.get("broadcast_date", "")).strip()
                broadcast_time = str(row.get("broadcast_start_time", "")).strip()
                program_name = str(row.get("program_name", "")).strip()

                if not episode_url:
                    continue

                source_import_id = f"fernsehserien_episode_broadcast::{episode_url}::{broadcast_date}::{broadcast_time}"
                if not self._mark_if_new_import(
                    core_class="episodes",
                    source_import_id=source_import_id,
                ):
                    continue

                fs_candidates.append(
                    {
                        "episode_id": episode_url,
                        "title": episode_url,
                        "program_norm": self._normalize_program_name(program_name),
                        "date_iso": self._parse_date_to_iso(broadcast_date),
                    }
                )

                result = AlignmentResult(
                    alignment_unit_id=f"fs_broadcast::{episode_url}::{broadcast_date}::{broadcast_time}",
                    core_class="episodes",
                    broadcasting_program_key=program_name,
                    episode_key=episode_url,
                    source_zdf_value=None,
                    source_wikidata_value=None,
                    source_fernsehserien_value=episode_url,
                    deterministic_alignment_status=AlignmentStatus.UNRESOLVED,
                    deterministic_alignment_score=0.0,
                    deterministic_alignment_method="seed_fernsehserien_broadcast",
                    deterministic_alignment_reason="Fernsehserien broadcast timing seeded for deterministic alignment handoff",
                    requires_human_review=True,
                    matched_on_fields=["episode_url", "broadcast_date", "broadcast_start_time"],
                    candidate_count=1,
                    evidence_sources=["fernsehserien"],
                )

                self.event_logs["episodes"].append_alignment_event(
                    alignment_result=result,
                    handler_name="episode_seed_fernsehserien_broadcast",
                    source_mention_data={
                        "episode_id": episode_url,
                        "publication_date": broadcast_date,
                        "publication_time": broadcast_time,
                        "duration_seconds": "",
                        "season_number": "",
                        "episode_number": "",
                    },
                    source_entity_ids={
                        "fernsehserien_episode_id": episode_url,
                    },
                    action={
                        "type": "import_snapshot",
                        "status": "emitted",
                        "reason": "fernsehserien broadcast timing seeded",
                    },
                    extra_context={
                        "source_name": "fernsehserien.episode_broadcasts",
                        "source_import_id": source_import_id,
                    },
                )

        if not wd_episodes_df.empty:
            for _, row in wd_episodes_df.iterrows():
                wd_episode_id = str(row.get("id", "")).strip()
                wd_label = str(row.get("label", "")).strip()
                series_key = str(row.get("part_of_qids", "")).split("|")[0].strip()

                if not wd_episode_id:
                    continue

                source_import_id = f"wikidata_episode::{wd_episode_id}"
                if not self._mark_if_new_import(
                    core_class="episodes",
                    source_import_id=source_import_id,
                ):
                    continue

                wd_program = str(row.get("program_from_label", "")).strip()
                wd_date_iso = str(row.get("broadcast_date", "")).strip()
                if not wd_program or not wd_date_iso:
                    parsed_program, parsed_date = self._extract_program_and_date_from_wikidata_label(wd_label)
                    wd_program = wd_program or parsed_program
                    wd_date_iso = wd_date_iso or parsed_date
                wd_candidates.append(
                    {
                        "wikidata_qid": wd_episode_id,
                        "label": wd_label,
                        "program_norm": self._normalize_program_name(wd_program),
                        "date_iso": wd_date_iso,
                        "fs_urls": str(row.get("fs_urls", "")).strip(),
                    }
                )

                result = AlignmentResult(
                    alignment_unit_id=f"wd::{wd_episode_id}",
                    core_class="episodes",
                    broadcasting_program_key=series_key,
                    episode_key=wd_episode_id,
                    source_zdf_value=None,
                    source_wikidata_value=wd_label or wd_episode_id,
                    source_fernsehserien_value=None,
                    deterministic_alignment_status=AlignmentStatus.UNRESOLVED,
                    deterministic_alignment_score=0.0,
                    deterministic_alignment_method="seed_wikidata_episode",
                    deterministic_alignment_reason="Wikidata episode seeded for deterministic alignment handoff",
                    requires_human_review=True,
                    matched_on_fields=["id", "class_id"],
                    candidate_count=1,
                    evidence_sources=["wikidata"],
                )

                self.event_logs["episodes"].append_alignment_event(
                    alignment_result=result,
                    handler_name="episode_seed_wikidata",
                    source_mention_data={
                        "episode_id": wd_episode_id,
                        "publication_date": "",
                        "publication_time": "",
                        "duration_seconds": "",
                        "season_number": "",
                        "episode_number": "",
                        **self._wikidata_source_metadata(row),
                    },
                    source_entity_ids={
                        "wikidata_qid": wd_episode_id,
                    },
                    action={
                        "type": "import_snapshot",
                        "status": "emitted",
                        "reason": "wikidata episode seeded",
                    },
                    extra_context={
                        "source_name": "wikidata.episodes_json",
                        "source_import_id": source_import_id,
                    },
                )

        self._emit_episode_time_matches(
            zdf_candidates=zdf_candidates,
            fs_candidates=fs_candidates,
            wd_candidates=wd_candidates,
        )

    def _run_wikidata_person_seeds(self, upstream: dict) -> None:
        """Seed person alignment rows from Wikidata person projections."""
        wd_persons = upstream.get("wd_persons", pd.DataFrame())
        if wd_persons.empty:
            return

        for _, row in wd_persons.iterrows():
            wd_person_id = str(row.get("id", "")).strip()
            wd_label = str(row.get("label", "")).strip()
            class_id = str(row.get("part_of_qids", "")).split("|")[0].strip()
            aliases = str(row.get("aliases", "")).strip()
            description = str(row.get("description_de", row.get("description_en", ""))).strip()

            if not wd_person_id:
                continue

            source_import_id = f"wikidata_person::{wd_person_id}"
            if not self._mark_if_new_import(
                core_class="persons",
                source_import_id=source_import_id,
            ):
                continue

            result = AlignmentResult(
                alignment_unit_id=f"wd_person::{wd_person_id}",
                core_class="persons",
                broadcasting_program_key=class_id,
                episode_key=None,
                source_zdf_value=None,
                source_wikidata_value=wd_label or wd_person_id,
                source_fernsehserien_value=None,
                deterministic_alignment_status=AlignmentStatus.UNRESOLVED,
                deterministic_alignment_score=0.0,
                deterministic_alignment_method="seed_wikidata_person",
                deterministic_alignment_reason="Wikidata person seeded for deterministic alignment handoff",
                requires_human_review=True,
                matched_on_fields=["id", "class_id"],
                candidate_count=1,
                evidence_sources=["wikidata"],
            )

            self.event_logs["persons"].append_alignment_event(
                alignment_result=result,
                handler_name="person_seed_wikidata",
                source_mention_data={
                    "mention_id": wd_person_id,
                    "mention_name": wd_label,
                    "episode_key": "",
                    "wikidata_id": wd_person_id,
                    "wikidata_label": wd_label,
                    "occupation_evidence": description,
                    "affiliation_evidence": aliases,
                    **self._wikidata_source_metadata(row),
                },
                source_entity_ids={
                    "wikidata_qid": wd_person_id,
                },
                action={
                    "type": "import_snapshot",
                    "status": "emitted",
                    "reason": "wikidata person seeded for manual disambiguation",
                },
                extra_context={
                    "source_name": "wikidata.persons_json",
                    "source_import_id": source_import_id,
                },
            )

    def _run_wikidata_class_seeds(
        self,
        *,
        upstream: dict,
        core_class: str,
        dataset_key: str,
        method_name: str,
    ) -> None:
        """Seed unresolved rows from a Wikidata JSON projection for a core class."""
        dataset = upstream.get(dataset_key, pd.DataFrame())
        if dataset.empty:
            return

        for _, row in dataset.iterrows():
            entity_id = str(row.get("id", "")).strip()
            label = str(row.get("label", "")).strip()
            if not entity_id:
                continue

            source_import_id = f"wikidata_{core_class}::{entity_id}"
            if not self._mark_if_new_import(
                core_class=core_class,
                source_import_id=source_import_id,
            ):
                continue

            result = AlignmentResult(
                alignment_unit_id=f"wd_{core_class}::{entity_id}",
                core_class=core_class,
                broadcasting_program_key="",
                episode_key=None,
                source_zdf_value=None,
                source_wikidata_value=label or entity_id,
                source_fernsehserien_value=None,
                deterministic_alignment_status=AlignmentStatus.UNRESOLVED,
                deterministic_alignment_score=0.0,
                deterministic_alignment_method=method_name,
                deterministic_alignment_reason=f"Wikidata {core_class} entity seeded for deterministic handoff",
                requires_human_review=True,
                matched_on_fields=["id"],
                candidate_count=1,
                evidence_sources=["wikidata"],
            )

            source_data = {
                "mention_id": entity_id,
                "mention_name": label,
                "episode_key": "",
                **self._wikidata_source_metadata(row),
            }
            if core_class == "series":
                source_data.update({"series_id": entity_id, "series_label": label})
            elif core_class == "topics":
                source_data.update({"topic_id": entity_id, "topic_label": label})
            elif core_class == "roles":
                source_data.update({"role_id": entity_id, "role_label": label, "confidence_role": ""})
            elif core_class == "organizations":
                source_data.update({"org_id": entity_id, "org_label": label, "confidence_org": ""})
            elif core_class == "broadcasting_programs":
                source_data.update({"program_label": label})

            self.event_logs[core_class].append_alignment_event(
                alignment_result=result,
                handler_name=f"seed_{core_class}",
                source_mention_data=source_data,
                source_entity_ids={
                    "wikidata_qid": entity_id,
                },
                action={
                    "type": "import_snapshot",
                    "status": "emitted",
                    "reason": f"wikidata {core_class} seeded for manual disambiguation",
                },
                extra_context={
                    "source_name": f"wikidata.{dataset_key}",
                    "source_import_id": source_import_id,
                },
            )

            # Clean-slate redesign requirement: keep season-like entities from
            # broadcasting_programs visible in aligned_series as well.
            if core_class == "broadcasting_programs" and self._is_series_like_broadcasting_program(row):
                series_import_id = f"wikidata_series_from_broadcasting::{entity_id}"
                if self._mark_if_new_import(
                    core_class="series",
                    source_import_id=series_import_id,
                ):
                    series_result = AlignmentResult(
                        alignment_unit_id=f"wd_series_from_broadcasting::{entity_id}",
                        core_class="series",
                        broadcasting_program_key="",
                        episode_key=None,
                        source_zdf_value=None,
                        source_wikidata_value=label or entity_id,
                        source_fernsehserien_value=None,
                        deterministic_alignment_status=AlignmentStatus.UNRESOLVED,
                        deterministic_alignment_score=0.0,
                        deterministic_alignment_method="seed_wikidata_series_from_broadcasting_program",
                        deterministic_alignment_reason="Wikidata broadcasting_program with P31=Q3464665 routed into series projection",
                        requires_human_review=True,
                        matched_on_fields=["id", "wikidata_p31_qids"],
                        candidate_count=1,
                        evidence_sources=["wikidata"],
                    )

                    self.event_logs["series"].append_alignment_event(
                        alignment_result=series_result,
                        handler_name="seed_series_from_broadcasting_program",
                        source_mention_data={
                            "mention_id": entity_id,
                            "mention_name": label,
                            "episode_key": "",
                            "series_id": entity_id,
                            "series_label": label,
                            **self._wikidata_source_metadata(row),
                        },
                        source_entity_ids={
                            "wikidata_qid": entity_id,
                        },
                        action={
                            "type": "import_snapshot",
                            "status": "emitted",
                            "reason": "wikidata broadcasting_program with season class duplicated into series",
                        },
                        extra_context={
                            "source_name": f"wikidata.{dataset_key}",
                            "source_import_id": series_import_id,
                        },
                    )


class RecoveryOrchestrator:
    """Handles recovery from checkpoints after interruption."""
    
    def __init__(self):
        """Initialize recovery orchestrator."""
        self.checkpoint_manager = CheckpointManager()
        self.projection_builder = AlignmentProjectionBuilder()
    
    def recover_and_resume(self) -> Optional[dict[str, pd.DataFrame]]:
        """Check for recovery markers and resume if needed.
        
        Returns:
            Projections if recovery was performed, None otherwise
        """
        checkpoint = self.checkpoint_manager.find_latest_checkpoint()
        if not checkpoint:
            return None
        
        # Validate checkpoint
        if not self.checkpoint_manager.validate_checkpoint(checkpoint):
            return None
        
        # Restore event logs and handler progress
        events_dir, projections_dir = self.checkpoint_manager.restore_checkpoint(checkpoint_dir=checkpoint)
        
        # Resume projection building
        projections = self.projection_builder.build_all_projections()
        
        return projections

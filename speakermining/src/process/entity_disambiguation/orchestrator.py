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
    EPISODES_CSV,
    FS_EPISODE_GUESTS,
    FS_EPISODE_METADATA,
    FS_EPISODE_BROADCASTS,
    PERSONS_CSV,
    PUBLICATIONS_CSV,
    WD_EPISODES,
    WD_PERSONS,
)
from .event_log import AlignmentEventLog
from .event_handlers import AlignmentProjectionBuilder
from .checkpoints import CheckpointManager
from .config import EVENTS_DIR


class Step311Orchestrator:
    """Orchestrates Step 311 automated disambiguation workflow."""
    
    def __init__(self):
        """Initialize orchestrator."""
        self.episode_aligner = EpisodeAligner()
        self.person_aligner = PersonAligner()
        self.program_aligner = BroadcastingProgramAligner()
        
        self.event_logs = {
            "persons": AlignmentEventLog(core_class="persons"),
            "episodes": AlignmentEventLog(core_class="episodes"),
            "broadcasting_programs": AlignmentEventLog(core_class="broadcasting_programs"),
        }
        
        self.projection_builder = AlignmentProjectionBuilder()
        self.checkpoint_manager = CheckpointManager()
        self._seen_import_ids: dict[str, set[str]] = {
            "persons": set(),
            "episodes": set(),
            "broadcasting_programs": set(),
        }
    
    def run(self) -> dict[str, pd.DataFrame]:
        """Run complete Step 311 workflow.
        
        Returns:
            Dict mapping core_class -> projection DataFrame
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

        def _read_csv_if_exists(path: Path) -> pd.DataFrame:
            if path.exists():
                return pd.read_csv(path)
            return pd.DataFrame()
        
        # Broadcasting programs (Layer 1)
        data["programs"] = _read_csv_if_exists(BROADCASTING_PROGRAMS_CSV)
        
        # Episodes (Layer 2)
        data["episodes"] = _read_csv_if_exists(EPISODES_CSV)
        data["candidate_episodes"] = _read_csv_if_exists(CANDIDATE_EPISODES_CSV)
        data["publications"] = _read_csv_if_exists(PUBLICATIONS_CSV)
        
        # Persons (Layer 3)
        data["persons"] = _read_csv_if_exists(PERSONS_CSV)
        data["wd_persons"] = _read_csv_if_exists(WD_PERSONS)
        data["wd_episodes"] = _read_csv_if_exists(WD_EPISODES)

        # Fernsehserien episode metadata (Layer 2 input)
        data["fs_episode_metadata"] = _read_csv_if_exists(FS_EPISODE_METADATA)
        data["fs_episode_broadcasts"] = _read_csv_if_exists(FS_EPISODE_BROADCASTS)

        # Fernsehserien episode guests (Layer 3 input)
        data["fs_episode_guests"] = _read_csv_if_exists(FS_EPISODE_GUESTS)
        
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
        text = str(value or "").strip()
        if not text:
            return ""
        text = text.casefold()
        text = re.sub(r"\([^)]*\)", " ", text)
        text = re.sub(r"\b\d{1,2}[.]\d{1,2}[.]\d{2,4}\b", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _parse_date_to_iso(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""

        parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
        if pd.notna(parsed):
            return parsed.strftime("%Y-%m-%d")

        # German month-name dates used in Wikidata labels, e.g. "12. Mai 2020"
        match = re.search(r"(\d{1,2})\.\s*([A-Za-zÄÖÜäöüß]+)\s+(\d{4})", text)
        if not match:
            return ""

        month_map = {
            "januar": 1,
            "februar": 2,
            "marz": 3,
            "märz": 3,
            "april": 4,
            "mai": 5,
            "juni": 6,
            "juli": 7,
            "august": 8,
            "september": 9,
            "oktober": 10,
            "november": 11,
            "dezember": 12,
        }

        day = int(match.group(1))
        month_raw = match.group(2).strip().casefold()
        year = int(match.group(3))
        month = month_map.get(month_raw)
        if not month:
            return ""

        try:
            return datetime(year=year, month=month, day=day).strftime("%Y-%m-%d")
        except ValueError:
            return ""

    @staticmethod
    def _extract_program_and_date_from_wikidata_label(label: str) -> tuple[str, str]:
        text = str(label or "").strip()
        if not text:
            return "", ""

        # Typical form: "Markus Lanz (22. Oktober 2024)"
        match = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", text)
        if match:
            program = match.group(1).strip()
            date_iso = Step311Orchestrator._parse_date_to_iso(match.group(2))
            return program, date_iso

        # Fallback: free text where a date appears somewhere in the label.
        date_iso = Step311Orchestrator._parse_date_to_iso(text)
        return text, date_iso

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
                }
        
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
                if episode_key in publication_first_by_episode:
                    if not person_episode_publication_date:
                        person_episode_publication_date = publication_first_by_episode[episode_key].get("date", "")
                    person_episode_publication_time = publication_first_by_episode[episode_key].get("time", "")

                source_import_id = f"zdf_person::{mention_id}"
                if not self._mark_if_new_import(
                    core_class="persons",
                    source_import_id=source_import_id,
                ):
                    continue
                
                # Run alignment
                result = self.person_aligner.align_person_in_episode(
                    episode_key=episode_key,
                    mention_id=mention_id,
                    mention_name=person_name,
                    wikidata_candidate=None,  # TODO: Load from candidate generation
                    fernsehserien_candidate=None,  # TODO: Load from candidate generation
                )
                
                # Set identifiers
                result.alignment_unit_id = f"{episode_key}:{mention_id}"
                result.broadcasting_program_key = broadcasting_program_key
                
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
                    },
                    source_entity_ids={
                        "zdf_mention_id": mention_id,
                        "zdf_episode_id": episode_key,
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
        episodes_df = upstream.get("episodes", pd.DataFrame())
        candidate_episodes_df = upstream.get("candidate_episodes", pd.DataFrame())
        publications_df = upstream.get("publications", pd.DataFrame())
        fs_meta_df = upstream.get("fs_episode_metadata", pd.DataFrame())
        fs_broadcasts_df = upstream.get("fs_episode_broadcasts", pd.DataFrame())
        wd_episodes_df = upstream.get("wd_episodes", pd.DataFrame())
        zdf_candidates: list[dict] = []
        fs_candidates: list[dict] = []
        wd_candidates: list[dict] = []

        pub_first = {}
        if not publications_df.empty and "episode_id" in publications_df.columns:
            pub_work = publications_df.copy()
            pub_work["episode_id"] = pub_work["episode_id"].astype(str)
            if "publication_index" in pub_work.columns:
                pub_work = pub_work.sort_values(by=["publication_index"])
            for _, prow in pub_work.iterrows():
                eid = str(prow.get("episode_id", "")).strip()
                if eid and eid not in pub_first:
                    pub_first[eid] = {
                        "date": str(prow.get("date", "")).strip(),
                        "time": str(prow.get("time", "")).strip(),
                        "duration": str(prow.get("duration", "")).strip(),
                        "program": str(prow.get("program", "")).strip(),
                    }

        zdf_source_df = candidate_episodes_df if not candidate_episodes_df.empty else episodes_df
        if not zdf_source_df.empty and "episode_id" in zdf_source_df.columns:
            zdf_rows = zdf_source_df.copy()
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

                program_name = str(row.get("sendungstitel", "")).strip()
                publication_date = self._first_available(
                    row,
                    [
                        "publication_data_0",
                        "publication_data_1",
                        "publication_data_2",
                        "publication_data_3",
                        "publikationsdatum",
                    ],
                    default="",
                )
                publication_time = ""
                duration = ""
                if episode_id in pub_first:
                    if not publication_date:
                        publication_date = pub_first[episode_id].get("date", "")
                    publication_time = pub_first[episode_id].get("time", "")
                    duration = pub_first[episode_id].get("duration", "")
                    if not program_name:
                        program_name = pub_first[episode_id].get("program", "")
                elif not publication_time:
                    publication_time = self._first_available(
                        row,
                        [
                            "publication_time_0",
                            "publication_time_1",
                            "publication_time_2",
                            "publication_time_3",
                        ],
                        default="",
                    )
                if not duration:
                    duration = self._first_available(
                        row,
                        [
                            "publication_duration_0",
                            "publication_duration_1",
                            "publication_duration_2",
                            "publication_duration_3",
                            "dauer",
                        ],
                        default="",
                    )

                date_iso = self._parse_date_to_iso(publication_date)
                program_norm = self._normalize_program_name(program_name)
                zdf_candidates.append(
                    {
                        "episode_id": episode_id,
                        "title": program_name,
                        "program_display": program_name,
                        "program_norm": program_norm,
                        "publication_date": publication_date,
                        "publication_time": publication_time,
                        "duration": duration,
                        "season_number": str(row.get("season", "")).strip(),
                        "episode_number": str(row.get("folge", "")).strip(),
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
                        "season_number": str(row.get("season", "")).strip(),
                        "episode_number": str(row.get("folge", "")).strip(),
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
                        "source_name": "mention_detection.episodes",
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
                wd_label = self._first_available(row, ["label_de", "label_en"], default="")
                series_key = str(row.get("class_id", "")).strip()

                if not wd_episode_id:
                    continue

                source_import_id = f"wikidata_episode::{wd_episode_id}"
                if not self._mark_if_new_import(
                    core_class="episodes",
                    source_import_id=source_import_id,
                ):
                    continue

                wd_program, wd_date_iso = self._extract_program_and_date_from_wikidata_label(wd_label)
                wd_candidates.append(
                    {
                        "wikidata_qid": wd_episode_id,
                        "label": wd_label,
                        "program_norm": self._normalize_program_name(wd_program),
                        "date_iso": wd_date_iso,
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
                        "source_name": "wikidata.instances_core_episodes",
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
            wd_label = self._first_available(row, ["label_de", "label_en"], default="")
            class_id = str(row.get("class_id", "")).strip()

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
                    "source_name": "wikidata.instances_core_persons",
                    "source_import_id": source_import_id,
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

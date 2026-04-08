from __future__ import annotations

# pyright: reportMissingImports=false

import json
from pathlib import Path

from process.candidate_generation.fernsehserien_de.config import FernsehserienRunConfig
from process.candidate_generation.fernsehserien_de.checkpoint import (
    FernsehserienCheckpointManifest,
    write_checkpoint_manifest,
)
from process.candidate_generation.fernsehserien_de.event_store import FernsehserienEventStore
from process.candidate_generation.fernsehserien_de.orchestrator import (
    _emit_normalized_events,
    _import_legacy_cached_episode_urls,
    _is_budget_exhausted,
)
from process.candidate_generation.fernsehserien_de.parser import (
    extract_neighbor_episode_urls,
    infer_episode_url_from_leaf_html,
    parse_episode_leaf_fields,
)
from process.candidate_generation.fernsehserien_de.paths import FernsehserienPaths
from process.candidate_generation.fernsehserien_de.projection import build_projections


def test_budget_minus_one_is_unlimited() -> None:
    assert _is_budget_exhausted(max_network_calls=-1, network_calls_used=0) is False
    assert _is_budget_exhausted(max_network_calls=-1, network_calls_used=10_000) is False
    assert _is_budget_exhausted(max_network_calls=0, network_calls_used=0) is True


def test_parser_emits_confidence_and_raw_overflow_json() -> None:
    html = """
    <h3 class=\"episode-output-titel\"><span itemprop=\"name\">Folge 1</span></h3>
    <div class=\"episoden-zeile-1000\"><div>75 Min.</div></div>
    <div class=\"episode-output-inhalt-inner\">Beschreibung</div>
    <h2 id=\"Cast-Crew\">Cast & Crew</h2>
    <ul class=\"cast-crew cast-crew-rest\">
      <a data-event-category=\"liste-cast-crew\" href=\"/alice/filmografie\" title=\"Alice\">
        <dl><dt itemprop=\"name\">Alice</dt><dd><p>Gast<br>Sangerin</p></dd></dl>
      </a>
    </ul>
    <h2 id=\"Sendetermine\">Sendetermine</h2>
    <section>
      <time itemprop=\"startDate\" datetime=\"2017-09-07T23:15:00+02:00\"></time>
      <time itemprop=\"endDate\" datetime=\"2017-09-08T00:30:00+02:00\"></time>
      <span itemprop=\"name\" content=\"ZDF\"></span>
    </section>
    """
    parsed = parse_episode_leaf_fields(html_text=html)

    assert isinstance(parsed.get("confidence"), float)
    assert parsed.get("guests_raw")
    assert parsed["guests_raw"][0]["confidence"] >= 0.7
    assert parsed.get("broadcasts_raw")
    assert parsed["broadcasts_raw"][0]["confidence"] >= 0.7

    raw_extra = json.loads(str(parsed.get("raw_extra_json", "{}")))
    assert raw_extra.get("guests_count") == 1
    assert raw_extra.get("broadcasts_count") == 1


def test_leaf_navigation_neighbor_extraction() -> None:
    html = """
    <a href=\"/markus-lanz/folgen/1001-foo\">zurueck</a>
    <a href=\"/markus-lanz/folgen/1003-bar\">weiter</a>
    """
    neighbors = extract_neighbor_episode_urls(
        html_text=html,
        base_url="https://www.fernsehserien.de/markus-lanz/folgen/1002-middle",
    )
    assert len(neighbors) == 2
    assert neighbors[0].startswith("https://www.fernsehserien.de/markus-lanz/folgen/")


def test_legacy_cache_import_emits_events(tmp_path: Path) -> None:
    repo_root = tmp_path
    paths = FernsehserienPaths(repo_root=repo_root)
    paths.ensure()

    cache_html = """
    <html>
      <head>
        <link rel=\"canonical\" href=\"https://www.fernsehserien.de/markus-lanz/folgen/1034-folge-1034\" />
      </head>
    </html>
    """
    (paths.cache_pages_dir / "legacy_a.html").write_text(cache_html, encoding="utf-8")

    event_store = FernsehserienEventStore(paths)
    known = set()
    imported = _import_legacy_cached_episode_urls(
        paths=paths,
        event_store=event_store,
        program_name="Markus Lanz",
        fernsehserien_de_id="markus-lanz",
        known_episode_urls=known,
    )

    assert imported == 1
    events = list(event_store.iter_events())
    event_types = [str(e.get("event_type", "")) for e in events]
    assert "legacy_cache_page_imported" in event_types
    assert "episode_url_discovered" in event_types


def test_infer_episode_url_from_leaf_html_prefers_canonical() -> None:
    html = '<link rel="canonical" href="https://www.fernsehserien.de/markus-lanz/folgen/1034-folge-1034" />'
    url = infer_episode_url_from_leaf_html(html_text=html)
    assert url == "https://www.fernsehserien.de/markus-lanz/folgen/1034-folge-1034"


def test_broadcast_normalization_handles_rollover(tmp_path: Path) -> None:
    repo_root = tmp_path
    paths = FernsehserienPaths(repo_root=repo_root)
    paths.ensure()
    event_store = FernsehserienEventStore(paths)

    event_store.append(
        event_type="episode_broadcast_discovered",
        payload={
            "program_name": "Markus Lanz",
            "episode_url": "https://www.fernsehserien.de/markus-lanz/folgen/1034-folge-1034",
            "broadcast_start_datetime_raw": "2017-09-07T23:15:00+02:00",
            "broadcast_end_datetime_raw": "2017-09-07T00:30:00+02:00",
            "broadcast_broadcaster_raw": "ZDF",
            "broadcast_is_premiere_raw": "TV-Premiere",
            "broadcast_order": 0,
        },
    )

    emitted = _emit_normalized_events(event_store=event_store)
    assert emitted == 1

    normalized = [e for e in event_store.iter_events() if str(e.get("event_type", "")) == "episode_broadcast_normalized"]
    assert len(normalized) == 1
    payload = normalized[0]["payload"]
    assert payload["broadcast_date"] == "2017-09-07"
    assert payload["broadcast_end_date"] == "2017-09-08"
    assert payload["broadcast_spans_next_day"] is True
    assert payload["broadcast_broadcaster_key"] == "zdf"


def test_run_config_exposes_unlimited_budget_flag(tmp_path: Path) -> None:
    config = FernsehserienRunConfig(repo_root=tmp_path, max_network_calls=-1)
    assert config.unlimited_network_budget is True


def test_run_config_defaults_to_all_eligible_programs(tmp_path: Path) -> None:
    config = FernsehserienRunConfig(repo_root=tmp_path)
    assert config.max_programs is None


def test_program_page_projection_dedupes_by_unique_program_id(tmp_path: Path) -> None:
    repo_root = tmp_path
    paths = FernsehserienPaths(repo_root=repo_root)
    paths.ensure()
    event_store = FernsehserienEventStore(paths)

    event_store.append(
        event_type="program_root_discovered",
        payload={
            "program_name": "Markus Lanz",
            "fernsehserien_de_id": "markus-lanz",
            "root_url": "https://www.fernsehserien.de/markus-lanz/",
            "fetched_at_utc": "2026-04-08T11:41:46Z",
        },
    )
    event_store.append(
        event_type="program_root_discovered",
        payload={
            "program_name": "Markus Lanz",
            "fernsehserien_de_id": "markus-lanz",
            "root_url": "https://www.fernsehserien.de/markus-lanz/",
            "fetched_at_utc": "2026-04-08T12:12:25Z",
        },
    )

    result = build_projections(paths=paths, event_store=event_store)
    assert result.summary["program_pages_rows"] == 1

    import pandas as pd

    program_pages = pd.read_csv(paths.projections_dir / "program_pages.csv")
    assert list(program_pages["fernsehserien_de_id"].unique()) == ["markus-lanz"]
    assert len(program_pages) == 1


def test_checkpoint_manifest_writes_snapshot_with_eventstore_payload(tmp_path: Path) -> None:
    repo_root = tmp_path
    paths = FernsehserienPaths(repo_root=repo_root)
    paths.ensure()

    # Minimal runtime artifacts
    (paths.projections_dir / "summary.json").write_text("{}\n", encoding="utf-8")
    (paths.chunks_dir / "chunk_000001.jsonl").write_text(
        '{"sequence_num":1,"event_type":"eventstore_opened","payload":{}}\n',
        encoding="utf-8",
    )

    manifest = FernsehserienCheckpointManifest(
        run_id="run_test",
        latest_checkpoint_timestamp="2026-04-08T15:00:00Z",
        phase="pipeline",
        programs_processed=1,
        network_calls_used=0,
        normalized_events_emitted=0,
    )
    checkpoint_path = write_checkpoint_manifest(repo_root, manifest)

    snapshot_dir = checkpoint_path.parent
    assert snapshot_dir.exists()
    assert (snapshot_dir / checkpoint_path.name).exists()
    assert (snapshot_dir / "files" / "summary.json").exists()
    assert (snapshot_dir / "eventstore" / "chunks" / "chunk_000001.jsonl").exists()
    assert (snapshot_dir / "eventstore" / "chunk_catalog.csv").exists()
    assert (snapshot_dir / "eventstore" / "eventstore_checksums.txt").exists()
    assert (paths.checkpoints_dir / "checkpoint_timeline.jsonl").exists()

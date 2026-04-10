from __future__ import annotations

# pyright: reportMissingImports=false

import json
from pathlib import Path

from process.notebook_event_log import NotebookEventLogger, get_or_create_notebook_logger
from process.candidate_generation.wikidata.cache import WIKIDATA_API_BASE, _http_get_json, begin_request_context, end_request_context


class _FakeResponse:
    def __init__(self, payload: str, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    def read(self) -> bytes:
        return self._payload.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_notebook_logger_appends_jsonl(tmp_path: Path) -> None:
    logger = NotebookEventLogger(
        repo_root=tmp_path,
        notebook_id="notebook_test",
        run_id="run_test_001",
    )
    logger.append_event(
        event_type="phase_started",
        phase="stage_a_graph_expansion",
        message="stage started",
    )
    logger.append_event(
        event_type="phase_finished",
        phase="stage_a_graph_expansion",
        message="stage finished",
    )

    lines = logger.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["notebook_id"] == "notebook_test"
    assert first["run_id"] == "run_test_001"
    assert first["event_type"] == "phase_started"
    assert second["event_type"] == "phase_finished"


def test_http_guardrail_emits_network_events(monkeypatch, tmp_path: Path) -> None:
    events: list[dict] = []

    def _capture_event(**payload) -> None:
        events.append(dict(payload))

    def _fake_urlopen(_req, timeout=30):  # noqa: ARG001
        return _FakeResponse('{"entities": {"Q1": {"id": "Q1"}}}', status=200)

    monkeypatch.setattr("process.candidate_generation.wikidata.cache.urlopen", _fake_urlopen)

    begin_request_context(
        budget_remaining=5,
        query_delay_seconds=0.0,
        progress_every_calls=0,
        context_label="test_context",
        event_emitter=_capture_event,
        event_phase="stage_a_graph_expansion",
    )
    try:
        payload = _http_get_json(f"{WIKIDATA_API_BASE}/Q1.json")
    finally:
        end_request_context()

    assert "entities" in payload
    event_types = [event.get("event_type", "") for event in events]
    assert "network_decision" in event_types
    assert "network_call_started" in event_types
    assert "network_call_finished" in event_types

    finished_events = [event for event in events if event.get("event_type") == "network_call_finished"]
    assert finished_events
    finished = finished_events[-1]
    assert finished.get("phase") == "stage_a_graph_expansion"
    assert finished.get("network", {}).get("request_kind") == "entity_by_qid"
    assert finished.get("result", {}).get("status") == "success"


def test_notebook_logger_repairs_malformed_jsonl_lines(tmp_path: Path) -> None:
    log_dir = tmp_path / "data" / "logs" / "notebooks"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "notebook_corrupt.events.jsonl"
    valid = json.dumps(
        {
            "timestamp_utc": "2026-04-01T10:00:00Z",
            "notebook_id": "notebook_corrupt",
            "run_id": "run_old",
            "phase": "run_lifecycle",
            "event_type": "run_started",
            "event_id": "evt_000001",
            "message": "old run",
        },
        ensure_ascii=False,
    )
    log_path.write_text(valid + "\n" + "{this is not json" + "\n", encoding="utf-8")

    logger = get_or_create_notebook_logger(tmp_path, "notebook_corrupt")
    logger.append_event(
        event_type="phase_started",
        phase="stage_a_graph_expansion",
        message="stage started",
    )

    parsed = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_types = [row.get("event_type") for row in parsed]
    assert "log_repaired" in event_types
    assert "run_started" in event_types
    assert "phase_started" in event_types

    corrupt_files = list(log_dir.glob("notebook_corrupt.events.jsonl.corrupt.*"))
    assert corrupt_files
    assert "{this is not json" in corrupt_files[-1].read_text(encoding="utf-8")


def test_notebook_logger_snapshot_recent_activity(tmp_path: Path) -> None:
    logger = NotebookEventLogger(
        repo_root=tmp_path,
        notebook_id="notebook_snapshot",
        run_id="run_snapshot_001",
    )
    logger.append_event(
        event_type="phase_started",
        phase="stage_a_graph_expansion",
        message="stage started",
        budget={"remaining": 10},
    )
    logger.append_event(
        event_type="runtime_heartbeat",
        phase="stage_a_graph_expansion",
        message="still running",
        rate_limit={"heartbeat_interval_seconds": 60},
        extra={"tick": 1},
    )

    snapshot = logger.snapshot_recent_activity(window_size=25)

    assert snapshot["events_seen"] == 2
    assert snapshot["latest_event_type"] == "runtime_heartbeat"
    assert snapshot["event_types_seen"]["phase_started"] == 1
    assert snapshot["event_types_seen"]["runtime_heartbeat"] == 1
    assert snapshot["top_event_types"][0]["event_type"] in {"phase_started", "runtime_heartbeat"}
    assert snapshot["latest_payload_snapshot"]["rate_limit"]["heartbeat_interval_seconds"] == 60

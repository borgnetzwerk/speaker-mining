from __future__ import annotations

import importlib
import json
import threading
import time


_FINISHED_RUN_IDS: set[tuple[str, str]] = set()


def _build_heartbeat_printer() -> tuple[dict, callable]:
    heartbeat_state = {
        "network_calls_used": 0,
        "programs_processed": 0,
        "events_in_window": 0,
        "event_type_counts": {},
        "last_event": {},
    }

    def _format_event_snapshot(event: dict) -> str:
        if not isinstance(event, dict) or not event:
            return "last_event=<none>"
        event_type = str(event.get("event_type", ""))
        sequence_num = int(event.get("sequence_num", 0) or 0)
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        payload_json = json.dumps(payload, ensure_ascii=False)
        if len(payload_json) > 320:
            payload_json = payload_json[:320] + "..."
        return f"last_event=seq:{sequence_num} type:{event_type} payload:{payload_json}"

    def heartbeat_printer(event: dict) -> None:
        kind = str(event.get("kind", ""))
        phase = str(event.get("phase", "pipeline"))

        if "network_calls_used" in event:
            heartbeat_state["network_calls_used"] = int(event.get("network_calls_used", 0))
        if "programs_processed" in event:
            heartbeat_state["programs_processed"] = int(event.get("programs_processed", 0))
        if "events_in_window" in event:
            heartbeat_state["events_in_window"] = int(event.get("events_in_window", 0))
        if "event_type_counts" in event and isinstance(event.get("event_type_counts"), dict):
            heartbeat_state["event_type_counts"] = dict(event.get("event_type_counts", {}))
        if "last_event" in event and isinstance(event.get("last_event"), dict):
            heartbeat_state["last_event"] = dict(event.get("last_event", {}))

        event_type_counts = heartbeat_state.get("event_type_counts", {})
        top_types = ", ".join(
            [f"{k}:{v}" for k, v in list(event_type_counts.items())[:5]]
        )
        if not top_types:
            top_types = "none"
        last_event_snapshot = _format_event_snapshot(heartbeat_state.get("last_event", {}))

        if kind == "minute":
            elapsed_seconds = int(event.get("elapsed_seconds", 0))
            print(
                f"[heartbeat:{phase}] +{elapsed_seconds}s "
                f"network_calls_used={heartbeat_state['network_calls_used']} "
                f"programs_processed={heartbeat_state['programs_processed']} "
                f"events_last_minute={heartbeat_state['events_in_window']} "
                f"event_types_last_minute={top_types} "
                f"{last_event_snapshot}",
                flush=True,
            )
        elif kind == "network_50":
            print(
                f"[heartbeat:{phase}] network milestone reached: "
                f"network_calls_used={heartbeat_state['network_calls_used']} "
                f"events_last_minute={heartbeat_state['events_in_window']} "
                f"{last_event_snapshot}",
                flush=True,
            )
        elif kind == "phase":
            print(
                f"[heartbeat:{phase}] normalization progress: "
                f"normalized_events_emitted={int(event.get('normalized_events_emitted', 0))} "
                f"events_last_minute={heartbeat_state['events_in_window']} "
                f"event_types_last_minute={top_types} "
                f"{last_event_snapshot}",
                flush=True,
            )
        elif kind == "checkpoint":
            print(
                f"[heartbeat:{phase}] checkpoint snapshot written: "
                f"{event.get('checkpoint_manifest_path', '')}",
                flush=True,
            )

    return heartbeat_state, heartbeat_printer


def _emit_run_finished_once(*, logger, final_result: dict, status: str = "success", message: str = "notebook run finished") -> bool:
    key = (str(logger.notebook_id), str(logger.run_id))
    if key in _FINISHED_RUN_IDS:
        return False

    logger.append_event(
        event_type="run_finished",
        phase="run_lifecycle",
        message=message,
        budget={
            "max_queries_per_run": int(final_result.get("max_network_calls", 0)),
            "queries_used_after": int(final_result.get("network_calls_used", 0)),
        },
        result={
            "programs_processed": int(final_result.get("programs_processed", 0)),
            "network_calls_used": int(final_result.get("network_calls_used", 0)),
            "max_network_calls": int(final_result.get("max_network_calls", 0)),
            "normalized_events_emitted": int(final_result.get("normalized_events_emitted", 0)),
            "checkpoint_manifest_path": str(final_result.get("checkpoint_manifest_path", "")),
            "status": status,
        },
    )
    _FINISHED_RUN_IDS.add(key)
    return True


def run_pipeline_with_notebook_heartbeat(*, config, logger) -> dict:
    """Run fernsehserien pipeline with notebook-friendly heartbeat and lifecycle logging."""
    from . import orchestrator as fsd_orchestrator

    importlib.reload(fsd_orchestrator)

    heartbeat_state, heartbeat_printer = _build_heartbeat_printer()

    # Local fallback heartbeat so progress remains visible if callback events are delayed.
    start_monotonic = time.monotonic()
    stop_heartbeat = threading.Event()

    def local_heartbeat_loop() -> None:
        while not stop_heartbeat.wait(60.0):
            elapsed_seconds = int(time.monotonic() - start_monotonic)
            event_type_counts = heartbeat_state.get("event_type_counts", {})
            top_types = ", ".join(
                [f"{k}:{v}" for k, v in list(event_type_counts.items())[:5]]
            )
            if not top_types:
                top_types = "none"
            print(
                f"[heartbeat:local] +{elapsed_seconds}s "
                f"still running network_calls_used={heartbeat_state['network_calls_used']} "
                f"programs_processed={heartbeat_state['programs_processed']} "
                f"events_last_minute={heartbeat_state['events_in_window']} "
                f"event_types_last_minute={top_types}",
                flush=True,
            )

    heartbeat_thread = threading.Thread(target=local_heartbeat_loop, daemon=True)
    heartbeat_thread.start()

    print("[heartbeat] workflow started", flush=True)
    heartbeat_printer(
        {
            "kind": "minute",
            "phase": "pipeline",
            "elapsed_seconds": 0,
            "network_calls_used": 0,
            "programs_processed": 0,
        }
    )

    final_result: dict | None = None
    interrupted = False
    try:
        try:
            final_result = fsd_orchestrator.run_fernsehserien_pipeline(
                config=config,
                notebook_logger=logger,
                heartbeat_callback=heartbeat_printer,
            )
        except KeyboardInterrupt:
            interrupted = True
            print("[heartbeat] interrupt received; stopping gracefully", flush=True)
            final_result = {
                "phase": "pipeline",
                "runtime_root": str(getattr(config, "repo_root", "")),
                "network_calls_used": int(heartbeat_state.get("network_calls_used", 0)),
                "max_network_calls": int(getattr(config, "max_network_calls", 0)),
                "programs_processed": int(heartbeat_state.get("programs_processed", 0)),
                "normalized_events_emitted": 0,
                "checkpoint_manifest_path": "",
                "status": "interrupted",
            }
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=1.0)

    print(
        f"programs_processed={final_result['programs_processed']} "
        f"network_calls_used={final_result['network_calls_used']} "
        f"max_network_calls={final_result['max_network_calls']} "
        f"normalized_events_emitted={final_result.get('normalized_events_emitted', 0)}"
    )
    print(f"checkpoint_manifest_path={final_result.get('checkpoint_manifest_path', '')}")

    if _emit_run_finished_once(
        logger=logger,
        final_result=final_result,
        status="interrupted" if interrupted else "success",
        message="notebook run interrupted" if interrupted else "notebook run finished",
    ):
        print("Lifecycle event emitted: run_finished")
    else:
        print("Lifecycle event already emitted for this run_id; skipping duplicate run_finished")

    return final_result

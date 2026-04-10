from __future__ import annotations

import signal
import threading
from pathlib import Path

from process.notebook_event_log import NOTEBOOK_21_ID, get_or_create_notebook_logger
from .graceful_shutdown import request_termination, reset_termination_flag
from .phase_contracts import PhaseContract, phase_contract_payload, phase_outcome_payload


def emit_event_derived_heartbeat(repo_root: Path, *, phase: str, window_size: int = 25) -> dict:
    logger = get_or_create_notebook_logger(repo_root, NOTEBOOK_21_ID)
    summary = logger.snapshot_recent_activity(window_size=window_size)
    summary["phase"] = phase
    top_types = summary.get("top_event_types", [])
    top_text = ", ".join(f"{row['event_type']}={row['count']}" for row in top_types) if top_types else "none"
    print(
        (
            f"[notebook] {phase} heartbeat (event-derived): "
            f"recent={summary['events_seen']} total={summary['total_events_emitted']} "
            f"top={top_text} latest={summary['latest_event_type']} "
            f"snapshot={summary['latest_payload_snapshot']}"
        ),
        flush=True,
    )
    return summary


def run_with_progress_heartbeat(
    repo_root: Path,
    *,
    phase: str,
    work_label: str,
    work_fn,
    heartbeat_interval_seconds: int,
    heartbeat_window_size: int,
) -> object:
    logger = get_or_create_notebook_logger(repo_root, NOTEBOOK_21_ID)
    stop_event = threading.Event()
    heartbeat_state: dict = {}
    interval_seconds = max(1, int(heartbeat_interval_seconds or 1))
    window_size = max(1, int(heartbeat_window_size or 25))
    contract = PhaseContract(
        phase=phase,
        owner="notebook_21_candidate_generation_wikidata",
        input_contract=f"{work_label}:inputs",
        output_contract=f"{work_label}:outputs",
    )
    terminal_status = "completed"

    # Keep previous handlers so notebook-local wiring remains reversible.
    previous_sigint = signal.getsignal(signal.SIGINT)
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def _interrupt_handler(signum, frame) -> None:
        _ = frame
        request_termination()
        logger.append_event(
            event_type="interrupt_requested",
            phase=phase,
            message=f"interrupt signal received ({signum}); requesting graceful stop",
            extra={"phase_contract": phase_contract_payload(contract)},
        )

    def _pump() -> None:
        logger.append_event(
            event_type="heartbeat_monitor_started",
            phase=phase,
            message=f"heartbeat monitor started for {work_label}",
            rate_limit={"heartbeat_interval_seconds": interval_seconds, "heartbeat_window_size": window_size},
            extra={"phase_contract": phase_contract_payload(contract)},
        )
        while not stop_event.wait(interval_seconds):
            heartbeat = emit_event_derived_heartbeat(repo_root, phase=phase, window_size=window_size)
            heartbeat_state.clear()
            heartbeat_state.update(heartbeat)
            logger.append_event(
                event_type="runtime_heartbeat",
                phase=phase,
                message=f"{work_label} still running",
                rate_limit={"heartbeat_interval_seconds": interval_seconds, "heartbeat_window_size": window_size},
                extra={
                    "heartbeat": heartbeat,
                    "phase_contract": phase_contract_payload(contract),
                },
            )

    thread = threading.Thread(target=_pump, name=f"{phase}_heartbeat", daemon=True)
    thread.start()
    try:
        reset_termination_flag()
        signal.signal(signal.SIGINT, _interrupt_handler)
        signal.signal(signal.SIGTERM, _interrupt_handler)
        return work_fn()
    except KeyboardInterrupt:
        terminal_status = "interrupted"
        logger.append_event(
            event_type="phase_interrupted",
            phase=phase,
            message=f"{work_label} interrupted by user",
            extra={
                "phase_contract": phase_contract_payload(contract),
                "last_heartbeat": dict(heartbeat_state),
                "phase_outcome": phase_outcome_payload(
                    phase=phase,
                    work_label=work_label,
                    status="interrupted",
                    details={"last_heartbeat": dict(heartbeat_state)},
                ),
            },
        )
        raise
    except Exception as exc:
        if "Termination requested" in str(exc):
            terminal_status = "interrupted"
        else:
            terminal_status = "failed"
        logger.append_event(
            event_type="phase_failed",
            phase=phase,
            message=f"{work_label} failed",
            extra={
                "phase_contract": phase_contract_payload(contract),
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "last_heartbeat": dict(heartbeat_state),
                "phase_outcome": phase_outcome_payload(
                    phase=phase,
                    work_label=work_label,
                    status="failed",
                    details={
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                    },
                ),
            },
        )
        raise
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
        stop_event.set()
        thread.join(timeout=interval_seconds + 1)
        final_heartbeat = emit_event_derived_heartbeat(repo_root, phase=phase, window_size=window_size)
        logger.append_event(
            event_type="heartbeat_monitor_stopped",
            phase=phase,
            message=f"heartbeat monitor stopped for {work_label}",
            extra={
                "phase_contract": phase_contract_payload(contract),
                "final_heartbeat": final_heartbeat,
                "phase_outcome": phase_outcome_payload(
                    phase=phase,
                    work_label=work_label,
                    status=terminal_status,
                    details={"final_heartbeat": final_heartbeat},
                ),
            },
        )
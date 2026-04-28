from __future__ import annotations

import os
import signal
import threading
from pathlib import Path

from process.notebook_event_log import NOTEBOOK_21_ID, get_or_create_notebook_logger
from .backoff_learning import AdaptiveBackoffController, append_backoff_learning_row
from .cache import get_request_context_query_delay_seconds, set_request_context_query_delay_seconds
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

    adaptive_controller = AdaptiveBackoffController(
        repo_root,
        phase=phase,
        interval_seconds=interval_seconds,
        pattern_heartbeats=int(os.getenv("WIKIDATA_ADAPTIVE_BACKOFF_PATTERN_HEARTBEATS", "3") or 3),
        increase_factor=float(os.getenv("WIKIDATA_ADAPTIVE_BACKOFF_INCREASE_FACTOR", "0.05") or 0.05),
        decrease_factor=float(os.getenv("WIKIDATA_ADAPTIVE_BACKOFF_DECREASE_FACTOR", "0.01") or 0.01),
        min_delay_seconds=float(os.getenv("WIKIDATA_ADAPTIVE_BACKOFF_MIN_DELAY_SECONDS", "0.05") or 0.05),
        max_delay_seconds=float(os.getenv("WIKIDATA_ADAPTIVE_BACKOFF_MAX_DELAY_SECONDS", "30.0") or 30.0),
        enabled=bool(int(os.getenv("WIKIDATA_ADAPTIVE_BACKOFF_ENABLED", "1") or 1)),
    )

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

            current_delay = float(get_request_context_query_delay_seconds())
            observation = adaptive_controller.observe_window(current_delay_seconds=current_delay)
            adjustment = adaptive_controller.decide_adjustment(current_delay_seconds=current_delay)
            if isinstance(adjustment, dict):
                new_delay = float(adjustment.get("new_delay_seconds", current_delay) or current_delay)
                previous_delay = float(adjustment.get("previous_delay_seconds", current_delay) or current_delay)
                if new_delay != previous_delay:
                    try:
                        effective = float(set_request_context_query_delay_seconds(new_delay))
                    except RuntimeError:
                        effective = float(previous_delay)
                    else:
                        print(
                            (
                                f"[notebook] {phase} adaptive delay: {previous_delay:.3f}s -> {effective:.3f}s "
                                f"reason={adjustment.get('reason', '')}"
                            ),
                            flush=True,
                        )
                        logger.append_event(
                            event_type="network_delay_adapted",
                            phase=phase,
                            message="adaptive query delay adjustment applied",
                            rate_limit={
                                "query_delay_seconds_configured": float(previous_delay),
                                "query_delay_seconds_effective": float(effective),
                                "backoff_factor": float(effective / previous_delay) if previous_delay > 0.0 else 1.0,
                            },
                            extra={
                                "action": str(adjustment.get("action", "")),
                                "reason": str(adjustment.get("reason", "")),
                                "window_calls": int(observation.get("window_calls", 0) or 0),
                                "window_backoffs": int(observation.get("window_backoffs", 0) or 0),
                            },
                        )
                        append_backoff_learning_row(
                            repo_root,
                            phase=phase,
                            action=str(adjustment.get("action", "")),
                            configured_delay_seconds=previous_delay,
                            new_delay_seconds=effective,
                            window_calls=int(observation.get("window_calls", 0) or 0),
                            window_backoffs=int(observation.get("window_backoffs", 0) or 0),
                            reason=str(adjustment.get("reason", "")),
                        )

            # Strip latest_payload_snapshot before storing; it recursively embeds
            # the previous heartbeat payload causing unbounded nesting (F22).
            heartbeat_for_event = {k: v for k, v in heartbeat.items() if k != "latest_payload_snapshot"}
            logger.append_event(
                event_type="runtime_heartbeat",
                phase=phase,
                message=f"{work_label} still running",
                rate_limit={"heartbeat_interval_seconds": interval_seconds, "heartbeat_window_size": window_size},
                extra={
                    "heartbeat": heartbeat_for_event,
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
        delay_summary = adaptive_controller.summarize_range()
        if delay_summary.get("safe_delay_range") or delay_summary.get("backoff_delay_range"):
            print(
                (
                    f"[notebook] {phase} adaptive delay summary: "
                    f"safe_range={delay_summary.get('safe_delay_range', [])} "
                    f"backoff_range={delay_summary.get('backoff_delay_range', [])} "
                    f"samples=(safe={delay_summary.get('safe_samples', 0)}, backoff={delay_summary.get('backoff_samples', 0)})"
                ),
                flush=True,
            )
            append_backoff_learning_row(
                repo_root,
                phase=phase,
                action="summary",
                configured_delay_seconds=float(get_request_context_query_delay_seconds()),
                new_delay_seconds=float(get_request_context_query_delay_seconds()),
                window_calls=int(delay_summary.get("safe_samples", 0) or 0) + int(delay_summary.get("backoff_samples", 0) or 0),
                window_backoffs=int(delay_summary.get("backoff_samples", 0) or 0),
                reason=(
                    f"safe_range={delay_summary.get('safe_delay_range', [])}; "
                    f"backoff_range={delay_summary.get('backoff_delay_range', [])}"
                ),
            )
        logger.append_event(
            event_type="heartbeat_monitor_stopped",
            phase=phase,
            message=f"heartbeat monitor stopped for {work_label}",
            extra={
                "phase_contract": phase_contract_payload(contract),
                "final_heartbeat": final_heartbeat,
                "adaptive_delay_summary": delay_summary,
                "phase_outcome": phase_outcome_payload(
                    phase=phase,
                    work_label=work_label,
                    status=terminal_status,
                    details={
                        "final_heartbeat": final_heartbeat,
                        "adaptive_delay_summary": delay_summary,
                    },
                ),
            },
        )
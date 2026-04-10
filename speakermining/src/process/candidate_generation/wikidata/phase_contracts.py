from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseContract:
    phase: str
    owner: str
    input_contract: str
    output_contract: str
    mode: str = "runtime"


def phase_contract_payload(contract: PhaseContract) -> dict:
    return {
        "phase": str(contract.phase),
        "owner": str(contract.owner),
        "mode": str(contract.mode),
        "input_contract": str(contract.input_contract),
        "output_contract": str(contract.output_contract),
    }


def phase_outcome_payload(
    *,
    phase: str,
    work_label: str,
    status: str,
    details: dict | None = None,
) -> dict:
    return {
        "phase": str(phase),
        "work_label": str(work_label),
        "status": str(status),
        "details": dict(details or {}),
    }

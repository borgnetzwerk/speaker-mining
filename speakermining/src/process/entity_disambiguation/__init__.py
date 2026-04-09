"""Phase 31 Step 311 Entity Disambiguation - Event-Sourced Orchestration.

This package implements deterministic, reproducible entity alignment following
the Layer 1-4 model specified in documentation/31_entity_disambiguation/311_automated_disambiguation_specification.md

Key modules:
- alignment: Deterministic matching logic (layers 1-4)
- event_log: Append-only event stream for reproducibility
- event_handlers: Replayable projection builders
- checkpoints: Snapshot and recovery infrastructure
- orchestrator: Top-level workflow coordination
"""
from __future__ import annotations

from .alignment import (
    AlignmentStatus,
    AlignmentResult,
    EpisodeAligner,
    PersonAligner,
    BroadcastingProgramAligner,
)
from .event_log import AlignmentEventLog
from .event_handlers import (
    HandlerProgressDB,
    ReplayableHandler,
    AlignmentProjectionBuilder,
)
from .checkpoints import CheckpointManager
from .orchestrator import Step311Orchestrator, RecoveryOrchestrator

__all__ = [
    "AlignmentStatus",
    "AlignmentResult",
    "EpisodeAligner",
    "PersonAligner",
    "BroadcastingProgramAligner",
    "AlignmentEventLog",
    "HandlerProgressDB",
    "ReplayableHandler",
    "AlignmentProjectionBuilder",
    "CheckpointManager",
    "Step311Orchestrator",
    "RecoveryOrchestrator",
]

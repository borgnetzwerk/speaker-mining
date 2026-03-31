"""
Text and identifier normalization utilities for Wikidata integration.

Provides functions to normalize text for matching and extract/validate Wikidata identifiers
(Q-IDs for entities, P-IDs for properties).
"""
from __future__ import annotations

import re
from typing import Iterable


_WS_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w]+", flags=re.UNICODE)
_QID_RE = re.compile(r"Q\d+")
_PID_RE = re.compile(r"P\d+")


def normalize_text(value: str) -> str:
    """
    Normalize text for canonical matching.
    
    Converts to lowercase, removes non-word characters, collapses whitespace.
    Used to create a canonical form of labels/names for matching mentions to candidates.
    
    Args:
        value: Input text (any type, will be coerced to string).
    
    Returns:
        Normalized text: lowercase, spaces-only whitespace, trimmed.
        Example: "Markus Lanz!" -> "markus lanz"
    """
    text = str(value or "").strip().lower()
    text = _NON_WORD_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def normalize_query_budget(value: int | str | None) -> int:
    """Normalize query budget values with strict semantics.

    Semantics:
    -1 => unlimited network queries
     0 => no network queries allowed
    >0 => finite budget

    Any value < -1 is invalid and raises ValueError.
    """
    if value is None:
        return 0
    budget = int(value)
    if budget < -1:
        raise ValueError("query budget must be -1 (unlimited), 0, or a positive integer")
    return budget


def canonical_qid(value: str) -> str:
    """
    Extract and validate a Wikidata entity Q-ID.
    
    A Q-ID (Qnnnnn) is Wikidata's unique identifier for an entity (person, place, work, etc.).
    This function searches for a Q-ID pattern in any input format: URI, raw text, etc.
    
    Args:
        value: Input text that may contain a Q-ID (e.g., "Q1499182", 
               "https://www.wikidata.org/wiki/Q1499182", "wd:Q1499182").
    
    Returns:
        Canonical Q-ID (uppercase) if found, empty string otherwise.
        Example: "https://www.wikidata.org/wiki/Q1499182" -> "Q1499182"
    """
    text = str(value or "").upper().strip()
    match = _QID_RE.search(text)
    return match.group(0) if match else ""


def canonical_pid(value: str) -> str:
    """
    Extract and validate a Wikidata property P-ID.
    
    A P-ID (Pnnnnn) is Wikidata's unique identifier for a property (has label, color, etc.).
    This function searches for a P-ID pattern in any input format: URI, raw text, etc.
    
    Args:
        value: Input text that may contain a P-ID (e.g., "P31", 
               "https://www.wikidata.org/wiki/Property:P31").
    
    Returns:
        Canonical P-ID (uppercase) if found, empty string otherwise.
    """
    text = str(value or "").upper().strip()
    match = _PID_RE.search(text)
    return match.group(0) if match else ""


def qid_from_uri(uri: str) -> str:
    """
    Extract a Q-ID from a Wikidata URI.
    
    Convenience wrapper around canonical_qid() for explicit URI parsing.
    
    Args:
        uri: Wikidata entity URI (e.g., "http://www.wikidata.org/entity/Q1499182").
    
    Returns:
        Q-ID if parseable, empty string otherwise.
    """
    text = str(uri or "")
    match = _QID_RE.search(text)
    return match.group(0) if match else ""


def pid_from_uri(uri: str) -> str:
    """
    Extract a P-ID from a Wikidata property URI.
    
    Convenience wrapper around canonical_pid() for explicit URI parsing.
    
    Args:
        uri: Wikidata property URI (e.g., "http://www.wikidata.org/prop/direct/P31").
    
    Returns:
        P-ID if parseable, empty string otherwise.
    """
    text = str(uri or "")
    match = _PID_RE.search(text)
    return match.group(0) if match else ""


def iter_entity_texts(entity_doc: dict) -> Iterable[str]:
    """
    Iterate over all text labels and aliases in a Wikidata entity document.
    
    Yields all human-readable labels and aliases (in any language) from the entity's
    `labels` and `aliases` fields. Used to build a comprehensive set of text signatures
    for matching against mention targets.
    
    Args:
        entity_doc: Wikidata entity JSON document (typically from API response).
    
    Yields:
        Text strings (labels and aliases) in the order they appear in the entity.
    """
    labels = entity_doc.get("labels", {})
    for info in labels.values():
        value = info.get("value", "")
        if value:
            yield value

    aliases = entity_doc.get("aliases", {})
    for alias_items in aliases.values():
        for info in alias_items:
            value = info.get("value", "")
            if value:
                yield value


def pick_entity_label(entity_doc: dict) -> str:
    """
    Select the best human-readable label for a Wikidata entity.
    
    Prefers German label (de) over English (en) for consistency with project context.
    Falls back to first available label if neither language is present.
    
    Args:
        entity_doc: Wikidata entity JSON document.
    
    Returns:
        Selected label string, or empty string if no labels exist.
    """
    for lang in ("de", "en"):
        value = entity_doc.get("labels", {}).get(lang, {}).get("value")
        if value:
            return value

    labels = entity_doc.get("labels", {})
    for info in labels.values():
        value = info.get("value")
        if value:
            return value

    return ""
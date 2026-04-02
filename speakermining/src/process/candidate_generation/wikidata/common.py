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
ENTITY_ROOT_QID = "Q35120"
DEFAULT_WIKIDATA_FALLBACK_LANGUAGE = "mul"
_DEFAULT_ACTIVE_WIKIDATA_LANGUAGES: tuple[str, ...] = ("de", "en")
_ACTIVE_WIKIDATA_LANGUAGES: tuple[str, ...] = _DEFAULT_ACTIVE_WIKIDATA_LANGUAGES


def _normalize_language_code(value: object) -> str:
    code = str(value or "").strip().lower()
    if not code:
        return ""
    return re.sub(r"[^a-z0-9-]+", "", code)


def resolve_enabled_wikidata_languages(language_spec: object) -> tuple[str, ...]:
    """Resolve enabled Wikidata languages from dict/list specs.

    - Dict input: includes keys where value is truthy.
    - Iterable input: includes non-empty values.
    - Empty resolved set raises ValueError with a user-facing message.
    """
    if isinstance(language_spec, dict):
        enabled = {
            _normalize_language_code(lang)
            for lang, flag in language_spec.items()
            if bool(flag) and _normalize_language_code(lang)
        }
    else:
        try:
            enabled = {
                _normalize_language_code(lang)
                for lang in (language_spec or [])
                if _normalize_language_code(lang)
            }
        except TypeError:
            enabled = set()

    if not enabled:
        raise ValueError("Please define at least one language")

    return tuple(sorted(enabled))


def set_active_wikidata_languages(language_spec: object) -> tuple[str, ...]:
    """Set active Wikidata languages used across extraction and matching helpers."""
    global _ACTIVE_WIKIDATA_LANGUAGES
    _ACTIVE_WIKIDATA_LANGUAGES = resolve_enabled_wikidata_languages(language_spec)
    return _ACTIVE_WIKIDATA_LANGUAGES


def get_active_wikidata_languages() -> tuple[str, ...]:
    """Return currently active Wikidata languages for this process."""
    return _ACTIVE_WIKIDATA_LANGUAGES


def active_wikidata_languages_with_default() -> tuple[str, ...]:
    """Return active languages plus the language-agnostic fallback bucket."""
    values = set(_ACTIVE_WIKIDATA_LANGUAGES)
    values.add(DEFAULT_WIKIDATA_FALLBACK_LANGUAGE)
    return tuple(sorted(values))


def projection_languages() -> tuple[str, ...]:
    """Return configured languages used for language-specific projection fields."""
    return get_active_wikidata_languages()


def language_projection_suffix(language_code: str) -> str:
    """Normalize language token for projection column/file suffixes."""
    token = _normalize_language_code(language_code).replace("-", "_")
    return token


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


def effective_core_class_qids(core_class_qids: set[str] | None) -> set[str]:
    """Normalize core-class set used for eligibility/subclass matching.

    The Wikidata class "entity" (Q35120) is treated as a root concept and must
    not qualify items as subclass/direct-instance of a project core class.
    """
    normalized = {canonical_qid(qid) for qid in (core_class_qids or set()) if canonical_qid(qid)}
    normalized.discard(ENTITY_ROOT_QID)
    return normalized


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
    allowed = set(active_wikidata_languages_with_default())
    labels = entity_doc.get("labels", {})
    for lang, info in labels.items():
        if allowed and str(lang or "").strip().lower() not in allowed:
            continue
        value = info.get("value", "")
        if value:
            yield value

    aliases = entity_doc.get("aliases", {})
    for lang, alias_items in aliases.items():
        if allowed and str(lang or "").strip().lower() not in allowed:
            continue
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
    for lang in list(get_active_wikidata_languages()) + [DEFAULT_WIKIDATA_FALLBACK_LANGUAGE]:
        value = entity_doc.get("labels", {}).get(lang, {}).get("value")
        if value:
            return value

    return ""
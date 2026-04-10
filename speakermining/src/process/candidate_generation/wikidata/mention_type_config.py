from __future__ import annotations

ALLOWED_MENTION_TYPES = {
    "person",
    "organization",
    "episode",
    "season",
    "topic",
    "broadcasting_program",
}


def normalize_mention_type_name(name) -> str:
    return str(name).strip().lower()


def resolve_enabled_mention_types(raw_config) -> list[str]:
    if isinstance(raw_config, dict):
        unknown = {
            normalize_mention_type_name(name)
            for name in raw_config
            if normalize_mention_type_name(name)
        } - ALLOWED_MENTION_TYPES
        if unknown:
            raise ValueError(
                "config['fallback_enabled_mention_types'] contains unsupported mention types: "
                f"{sorted(unknown)}. Allowed: {sorted(ALLOWED_MENTION_TYPES)}"
            )
        enabled = {
            normalize_mention_type_name(name)
            for name, is_enabled in raw_config.items()
            if normalize_mention_type_name(name) and bool(is_enabled)
        }
        return sorted(enabled)

    if isinstance(raw_config, (list, tuple, set)):
        normalized = {
            normalize_mention_type_name(value)
            for value in raw_config
            if normalize_mention_type_name(value)
        }
        unknown = normalized - ALLOWED_MENTION_TYPES
        if unknown:
            raise ValueError(
                "config['fallback_enabled_mention_types'] contains unsupported mention types: "
                f"{sorted(unknown)}. Allowed: {sorted(ALLOWED_MENTION_TYPES)}"
            )
        return sorted(normalized)

    raise ValueError(
        "config['fallback_enabled_mention_types'] must be a dict or list/tuple/set of mention types."
    )


def snapshot_enabled_mention_types(raw_config) -> tuple[tuple[str, bool], ...]:
    if not isinstance(raw_config, dict):
        raise ValueError(
            "config['fallback_enabled_mention_types'] must stay a dict after Step 2. Re-run the workflow configuration cell."
        )
    return tuple(
        sorted(
            (
                normalize_mention_type_name(name),
                bool(is_enabled),
            )
            for name, is_enabled in raw_config.items()
            if normalize_mention_type_name(name)
        )
    )


def assert_mention_type_snapshot_unchanged(
    raw_config,
    expected_snapshot: tuple[tuple[str, bool], ...],
    *,
    context: str,
) -> None:
    if not isinstance(expected_snapshot, tuple):
        raise ValueError(
            "config['_fallback_enabled_mention_types_snapshot'] missing. Re-run the workflow configuration cell (Step 2)."
        )
    current_snapshot = snapshot_enabled_mention_types(raw_config)
    if current_snapshot != expected_snapshot:
        raise RuntimeError(
            f"config['fallback_enabled_mention_types'] changed after Step 2. Re-run the workflow configuration cell before {context}."
        )
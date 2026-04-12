from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

import pandas as pd


_TITLE_PATTERN = re.compile(
    r"^\s*(dr\.?|prof\.?|herr|frau|mr\.?|mrs\.?|ms\.?|sir)\s+",
    flags=re.IGNORECASE,
)


def normalize_name(value: object) -> str:
    """Normalize a person/entity name for deterministic matching.
    
    Performs deterministic transformations to enable reliable cross-source comparison:
    - Removes titles (Dr., Prof., Herr, Frau, etc.)
    - Removes parenthetical qualifiers (job titles, disambiguation)
    - German umlauts → ASCII equivalent (ä→ae, ö→oe, ü→ue, ß→ss)
    - Case-folding to lowercase
    - Non-alphanumeric → spaces (except hyphens)
    - Multiple spaces → single space
    - Trim leading/trailing whitespace
    
    Args:
        value: Input name (any type, will be converted to string)
    
    Returns:
        Normalized name string, empty string if input is None/empty
    
    Examples:
        >>> normalize_name("Dr. Georg Pieper")
        'georg pieper'
        >>> normalize_name("Verona Pooth (TV Host)")
        'verona pooth'
        >>> normalize_name("Müller-Schäfer")
        'mueller schaefer'
    """
    text = str(value or "").strip()
    if not text:
        return ""

    text = re.sub(r"\([^)]*\)", " ", text)
    text = _TITLE_PATTERN.sub("", text)
    text = (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("Ä", "Ae")
        .replace("Ö", "Oe")
        .replace("Ü", "Ue")
        .replace("ß", "ss")
    )
    text = text.casefold()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(r"[-_]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_program_name(value: object) -> str:
    """Normalize broadcasting program name for matching.
    
    Removes dates and parenthetical qualifiers which vary across sources.
    Enables matching of show names across ZDF, Wikidata, Fernsehserien.
    
    Args:
        value: Program name (e.g., "Markus Lanz (03.06.2008)")
    
    Returns:
        Normalized program name, empty string if input is None/empty
    
    Examples:
        >>> normalize_program_name("Markus Lanz (03.06.2008)")
        'markus lanz'
        >>> normalize_program_name("Tagesthemen (Wiederholung)")
        'tagesthemen'
    """
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.casefold()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b\d{1,2}[.]\d{1,2}[.]\d{2,4}\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_date_to_iso(value: object) -> str:
    """Parse dates from multiple formats into ISO 8601 (YYYY-MM-DD).
    
    Handles:
    - ISO 8601 dates (2008-06-03)
    - German dot notation (03.06.2008)
    - German month words (3. Juni 2008, 3. Juni 2004)
    - Pandas-recognized formats
    
    Args:
        value: Date string in any supported format
    
    Returns:
        ISO 8601 date string (YYYY-MM-DD), empty string if parsing fails or input is None
    
    Examples:
        >>> parse_date_to_iso("03.06.2008")
        '2008-06-03'
        >>> parse_date_to_iso("3. Juni 2008")
        '2008-06-03'
        >>> parse_date_to_iso("2008-06-03")
        '2008-06-03'
    """
    text = str(value or "").strip()
    if not text:
        return ""

    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    if pd.notna(parsed):
        return parsed.strftime("%Y-%m-%d")

    match = re.search(r"(\d{1,2})\.\s*([A-Za-z]+)\s+(\d{4})", text)
    if not match:
        return ""

    month_map = {
        "januar": 1,
        "februar": 2,
        "maerz": 3,
        "marz": 3,
        "april": 4,
        "mai": 5,
        "juni": 6,
        "juli": 7,
        "august": 8,
        "september": 9,
        "oktober": 10,
        "november": 11,
        "dezember": 12,
    }

    day = int(match.group(1))
    month_raw = match.group(2).strip().casefold()
    month = month_map.get(month_raw)
    year = int(match.group(3))
    if not month:
        return ""

    try:
        return datetime(year=year, month=month, day=day).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def name_similarity(name_left: object, name_right: object) -> float:
    """Deterministic similarity score for person names (0.0 to 1.0).
    
    Uses only normalized string matching (no fuzzy algorithms).
    Scoring tiers:
    - 1.0: Exactly equal after normalization
    - 0.7: One name is substring of other (after normalization)
    - 0.0: No match
    
    Args:
        name_left: First name to compare
        name_right: Second name to compare
    
    Returns:
        Similarity score: 1.0 (exact), 0.7 (substring), or 0.0 (no match)
    
    Examples:
        >>> name_similarity("Verona Pooth", "verona pooth")
        1.0
        >>> name_similarity("Georg Pieper", "pieper")
        0.7
        >>> name_similarity("John Smith", "Jane Doe")
        0.0
    """
    left = normalize_name(name_left)
    right = normalize_name(name_right)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if left in right or right in left:
        return 0.7
    return 0.0


def extract_label_and_date_from_parenthetical(label: object) -> tuple[str, str]:
    """Split Wikidata labels containing dates into program name and ISO date.
    
    Handles patterns like 'Show Name (16. Januar 2025)' and extracts both components.
    If no parenthetical is found, attempts to parse the entire string as a date.
    
    Args:
        label: Label string potentially containing parenthetical date
    
    Returns:
        Tuple of (program_name, iso_date_string)
        - Empty strings returned for components that cannot be extracted
    
    Examples:
        >>> extract_label_and_date_from_parenthetical('Markus Lanz (3. Juni 2008)')
        ('Markus Lanz', '2008-06-03')
        >>> extract_label_and_date_from_parenthetical('2008-06-03')
        ('', '2008-06-03')
    """
    text = str(label or "").strip()
    if not text:
        return "", ""

    match = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", text)
    if match:
        return match.group(1).strip(), parse_date_to_iso(match.group(2))

    return text, parse_date_to_iso(text)


def parse_duration_to_seconds(value: object) -> Optional[int]:
    """Parse video durations into seconds.
    
    Handles multiple formats:
    - German format: 69'54 (69 minutes, 54 seconds)
    - Abbreviated: 59' (59 minutes, 0 seconds)
    - ISO 8601 duration strings (via pandas.to_timedelta)
    
    Args:
        value: Duration string in any supported format
    
    Returns:
        Duration in seconds as int, None if parsing fails or input is None
    
    Examples:
        >>> parse_duration_to_seconds("69'54")
        4194
        >>> parse_duration_to_seconds("59'")
        3540
        >>> parse_duration_to_seconds("PT1H2M3S")
        3723
    """
    text = str(value or "").strip()
    if not text:
        return None

    match = re.match(r"^(\d+)\s*'\s*(\d{1,2})?$", text)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2) or "0")
        return minutes * 60 + seconds

    parsed = pd.to_timedelta(text, errors="coerce")
    if pd.notna(parsed):
        return int(parsed.total_seconds())

    return None

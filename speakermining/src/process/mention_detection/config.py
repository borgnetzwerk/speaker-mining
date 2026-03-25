from __future__ import annotations

from pathlib import Path


# Phase-local paths. This module is intentionally scoped to mention detection.
DATA_DIR = Path("data")
INPUT_DIR = DATA_DIR / "01_input"
PHASE_DIR = DATA_DIR / "10_mention_detection"

ZDF_ARCHIVE_DIR = INPUT_DIR / "zdf_archive"


# Contract file names for phase outputs.
FILE_EPISODES = "episodes.csv"
FILE_PERSON_MENTIONS = "persons.csv"
FILE_INSTITUTION_MENTIONS = "institutions.csv"
FILE_TOPIC_MENTIONS = "topics.csv"
FILE_SEASONS = "seasons.csv"
FILE_PUBLIKATION = "publications.csv"


EPISODE_COLUMNS = [
    "episode_id",
    "sendungstitel",
    "publikation_id",
    "publikationsdatum",
    "dauer",
    "archivnummer",
    "prod_nr_beitrag",
    "zeit_tc_start",
    "zeit_tc_end",
    "season",
    "staffel",
    "folge",
    "folgennr",
    "infos",
]

PERSON_MENTION_COLUMNS = [
    "mention_id",
    "episode_id",
    "name",
    "beschreibung",
    "source_text",
]

PUBLIKATION_COLUMNS = [
    "publikation_id",
    "episode_id",
    "publication_index",
    "date",
    "time",
    "duration",
    "program",
    "prod_nr_sendung",
    "prod_nr_secondary",
    "is_primary",
    "raw_line",
]

INSTITUTION_MENTION_COLUMNS = [
    "mention_id",
    "episode_id",
    "institution",
    "source_text",
]

TOPIC_MENTION_COLUMNS = [
    "mention_id",
    "episode_id",
    "topic",
    "source_text",
]

SEASON_COLUMNS = [
    "season_id",
    "season_label",
    "start_time",
    "end_time",
    "episode_count",
]


DEFAULT_PDF_TXT_INPUTS = [
    "Markus Lanz_2008-2010.pdf_episodes.txt",
    "Markus Lanz_2011-2015.pdf_episodes.txt",
    "Markus Lanz_2016-2020.pdf_episodes.txt",
    "Markus Lanz_2021-2024.pdf_episodes.txt",
]

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


EPISODE_COLUMNS = [
    "episode_id",
    "sendungstitel",
    "publikationsdatum",
    "dauer",
    "season",
    "staffel",
    "folge",
    "folgennr",
    "infos",
    "instance_of",
    "part_of_series",
    "genre",
    "presenter",
    "original_broadcaster",
    "country_of_origin",
    "original_language_of_film_or_tv_show",
]

PERSON_MENTION_COLUMNS = [
    "mention_id",
    "episode_id",
    "name",
    "beschreibung",
    "source_text",
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
    "instance_of",
    "part_of_series",
    "genre",
    "presenter",
    "original_broadcaster",
    "country_of_origin",
    "original_language_of_film_or_tv_show",
]


DEFAULT_PDF_TXT_INPUTS = [
    "Markus Lanz_2008-2010.pdf_episodes.txt",
    "Markus Lanz_2011-2015.pdf_episodes.txt",
    "Markus Lanz_2016-2020.pdf_episodes.txt",
    "Markus Lanz_2021-2024.pdf_episodes.txt",
]

"""
Layer 1a: Person-Episode Occurrence Matrix

Implements TASK-B02: Build person-episode occurrence matrices.
Responsibilities:
- Build person catalogue with role classification, appearance counts, and Wikidata properties
- Build guest × episode occurrence matrices (per scope + combined)
- Compute co-occurrence matrix for top guests

Requirements: REQ-G01, REQ-G02, REQ-G03
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Set, Optional


def _item_qid(stmt):
    """Extract QID from Wikidata statement."""
    try:
        return stmt["mainsnak"]["datavalue"]["value"]["id"]
    except (KeyError, TypeError):
        return ""


def _time_year(stmt):
    """Extract year from Wikidata time value."""
    try:
        t = stmt["mainsnak"]["datavalue"]["value"]["time"]
        return t[1:5]
    except (KeyError, TypeError):
        return ""


def extract_wikidata_properties(entity_doc):
    """
    Extract Phase 5 Wikidata properties from an entity document.
    
    Args:
        entity_doc: Wikidata entity JSON (or None)
        
    Returns:
        Tuple of (gender_qid, occ_qids, party_qids, employer_qids, birthyear, bp_qid)
    """
    if not entity_doc:
        return "", [], [], [], "", ""
    
    claims = entity_doc.get("claims", {})
    
    gender_qid = _item_qid(claims["P21"][0]) if "P21" in claims else ""
    occ_qids = [_item_qid(s) for s in claims.get("P106", []) if _item_qid(s)]
    party_qids = [_item_qid(s) for s in claims.get("P102", []) if _item_qid(s)]
    employer_qids = [_item_qid(s) for s in claims.get("P108", []) if _item_qid(s)]
    birthyear = _time_year(claims["P569"][0]) if "P569" in claims else ""
    bp_qid = _item_qid(claims["P19"][0]) if "P19" in claims else ""
    
    return gender_qid, occ_qids, party_qids, employer_qids, birthyear, bp_qid


def build_person_catalogue(
    dedup_persons: pd.DataFrame,
    cluster_members: pd.DataFrame,
    episode_meta: pd.DataFrame,
    in_scope_show_ids: Set[str],
    core_persons: Dict,
    qid_label: Dict[str, str],
    moderator_qids: Optional[Set[str]] = None,
    repo_root: Optional[Path] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Build person catalogue with role classification, appearance counts, and Wikidata properties.

    Args:
        dedup_persons: Phase 32 entity deduplication results.
        cluster_members: Phase 32 cluster membership records.
        episode_meta: Episode metadata for show filtering and ordering.
        in_scope_show_ids: Set of show IDs to include in analysis.
        core_persons: Archive Wikidata entity cache (QID → entity doc).
        qid_label: QID → human-readable label mapping.
        moderator_qids: Optional set of known moderator QIDs.

    Returns:
        Tuple of (catalogue, unmatched, unclassified, ri_with_role, episode_appearances).
    """
    if moderator_qids is None:
        moderator_qids = set()

    role_map = {
        "Gast": "guest",
        "Kommentar": "guest",
        "Kommentator": "guest",
        "": "guest",
        "Moderation": "moderator",
        "Produktionsauftrag": "staff",
        "Produktionsfirma": "staff",
        "Redaktion": "staff",
        "Regie": "staff",
        "Drehbuch": "staff",
    }
    role_priority = {"guest": 0, "moderator": 1, "staff": 2, "incidental": 3}

    member_df = cluster_members.copy()
    if member_df.empty:
        member_df = pd.DataFrame(columns=[
            "canonical_entity_id",
            "alignment_unit_id",
            "canonical_label",
            "wikidata_id",
            "mention_id",
            "match_tier",
            "fernsehserien_de_id_fernsehserien_de",
            "guest_role_fernsehserien_de",
            "episode_url_fernsehserien_de",
        ])

    if "fernsehserien_de_id_fernsehserien_de" in member_df.columns:
        member_df["show_id"] = member_df["fernsehserien_de_id_fernsehserien_de"].astype(str).str.strip()
    else:
        member_df["show_id"] = ""

    if "episode_url_fernsehserien_de" in member_df.columns:
        member_df["episode_url"] = member_df["episode_url_fernsehserien_de"].astype(str).str.strip()
    else:
        member_df["episode_url"] = ""

    guest_role_series = member_df["guest_role_fernsehserien_de"] if "guest_role_fernsehserien_de" in member_df.columns else pd.Series("", index=member_df.index)
    member_df["role"] = guest_role_series.astype(str).map(role_map).fillna("guest")
    member_df.loc[member_df["wikidata_id"].isin(moderator_qids), "role"] = "moderator"

    in_scope_episode_urls = set(
        episode_meta[episode_meta["fernsehserien_de_id"].isin(in_scope_show_ids)]["episode_url"].astype(str).str.strip()
    )

    in_scope_members = member_df[
        member_df["show_id"].isin(in_scope_show_ids) & member_df["episode_url"].isin(in_scope_episode_urls)
    ].copy()

    app_counts_s = (
        in_scope_members[in_scope_members["canonical_entity_id"].notna()]
        .groupby("canonical_entity_id")["episode_url"]
        .nunique()
        .rename("appearance_count")
        .reset_index()
    )

    dominant_role_s = (
        in_scope_members[in_scope_members["canonical_entity_id"].notna()]
        .groupby("canonical_entity_id")["role"]
        .agg(lambda roles: min(roles, key=lambda r: role_priority.get(r, 9)))
        .rename("role")
        .reset_index()
    )

    catalogue = dedup_persons[[
        "canonical_entity_id", "wikidata_id", "canonical_label",
        "cluster_size", "cluster_strategy", "cluster_confidence"
    ]].copy()

    catalogue = catalogue.merge(dominant_role_s, on="canonical_entity_id", how="left")
    catalogue = catalogue.merge(app_counts_s, on="canonical_entity_id", how="left")
    catalogue["role"] = catalogue["role"].fillna("incidental")
    catalogue.loc[catalogue["wikidata_id"].isin(moderator_qids), "role"] = "moderator"
    catalogue["appearance_count"] = catalogue["appearance_count"].fillna(0).astype(int)

    _get_cached = None
    if repo_root is not None:
        try:
            from process.candidate_generation.wikidata.entity_access import get_cached_entity_doc as _gc
            _get_cached = _gc
        except Exception:
            pass

    prop_records = []
    _archive_hits = 0
    _cache_hits = 0
    _misses = 0
    for _, row in catalogue.iterrows():
        qid = row["wikidata_id"]
        entity = None

        if qid:
            entity = core_persons.get(qid)
            if entity:
                _archive_hits += 1
            elif _get_cached is not None:
                try:
                    entity = _get_cached(qid, repo_root)
                    if entity:
                        _cache_hits += 1
                    else:
                        _misses += 1
                except Exception:
                    _misses += 1
            else:
                _misses += 1

        claims = entity.get("claims", {}) if entity else {}
        if claims:
            gender_qid, occ_qids, party_qids, employer_qids, birthyear, bp_qid = extract_wikidata_properties(entity)
            gender = qid_label.get(gender_qid, gender_qid) if gender_qid else ""
            birthplace = qid_label.get(bp_qid, bp_qid) if bp_qid else ""
            occ_labels = [qid_label.get(q, q) for q in occ_qids]
            pty_labels = [qid_label.get(q, q) for q in party_qids]
            emp_labels = [qid_label.get(q, q) for q in employer_qids]
        else:
            gender_qid = gender = birthyear = bp_qid = birthplace = ""
            occ_qids = party_qids = employer_qids = []
            occ_labels = pty_labels = emp_labels = []

        prop_records.append({
            "canonical_entity_id": row["canonical_entity_id"],
            "gender": gender, "gender_qid": gender_qid,
            "birthyear": birthyear, "birthplace": birthplace, "birthplace_qid": bp_qid,
            "occupations": "|".join(occ_labels), "occupation_qids": "|".join(occ_qids),
            "party": "|".join(pty_labels), "party_qids": "|".join(party_qids),
            "employer": "|".join(emp_labels), "employer_qids": "|".join(employer_qids),
        })

    print(f"  Wikidata property coverage: archive={_archive_hits:,}  cache={_cache_hits:,}  missing={_misses:,}")

    props_df = pd.DataFrame(prop_records)
    catalogue = catalogue.merge(props_df, on="canonical_entity_id", how="left")

    CATALOGUE_COLS = [
        "canonical_entity_id", "wikidata_id", "canonical_label", "cluster_size",
        "cluster_strategy", "cluster_confidence", "role", "appearance_count",
        "gender", "gender_qid", "birthyear", "birthplace", "birthplace_qid",
        "occupations", "occupation_qids", "party", "party_qids", "employer", "employer_qids",
    ]
    catalogue = catalogue[CATALOGUE_COLS]

    unmatched = catalogue[catalogue["wikidata_id"] == ""]
    unclassified = catalogue[catalogue["appearance_count"] == 0]

    episode_appearances = in_scope_members[in_scope_members["canonical_entity_id"].notna()].copy()
    if not episode_appearances.empty:
        episode_appearances = episode_appearances.rename(columns={
            "episode_url": "episode_id",
            "raw_role": "role",
        })
        episode_appearances = episode_appearances.merge(
            catalogue[["canonical_entity_id", "wikidata_id", "canonical_label", "appearance_count", "birthyear"]],
            on="canonical_entity_id",
            how="left",
        )
        # Always derive guest_qid from canonical catalogue linkage, not from
        # cluster membership rows, which may lack resolved Wikidata IDs.
        if "wikidata_id_y" in episode_appearances.columns:
            episode_appearances["wikidata_id"] = episode_appearances["wikidata_id_y"].fillna(
                episode_appearances.get("wikidata_id_x", "")
            )
        elif "wikidata_id" not in episode_appearances.columns and "wikidata_id_x" in episode_appearances.columns:
            episode_appearances["wikidata_id"] = episode_appearances["wikidata_id_x"]

        qid_series = pd.Series("", index=episode_appearances.index, dtype=str)
        for qid_col in ("wikidata_id", "wikidata_id_y", "wikidata_id_x"):
            if qid_col in episode_appearances.columns:
                candidate = episode_appearances[qid_col].fillna("").astype(str).str.strip()
                qid_series = qid_series.where(qid_series.str.strip() != "", candidate)

        episode_appearances["guest_qid"] = qid_series.astype(str).str.strip()
        episode_appearances["premiere_date"] = episode_appearances["episode_id"].map(
            episode_meta.set_index("episode_url")["premiere_date"].to_dict()
        )
        episode_appearances["show_id"] = episode_appearances["show_id"].astype(str)
    else:
        episode_appearances = pd.DataFrame(columns=[
            "canonical_entity_id", "alignment_unit_id", "mention_id", "canonical_label",
            "wikidata_id", "match_tier", "cluster_key", "is_representative",
            "fernsehserien_de_id", "fernsehserien_de_id_fernsehserien_de", "program_name_fernsehserien_de",
            "episode_url_fernsehserien_de", "guest_name_fernsehserien_de", "guest_role_fernsehserien_de",
            "guest_description_fernsehserien_de", "source_event_sequence_fernsehserien_de", "show_id",
            "episode_id", "role", "guest_qid", "canonical_label", "appearance_count", "birthyear", "premiere_date",
        ])

    return catalogue, unmatched, unclassified, in_scope_members, episode_appearances


def build_occurrence_matrix(
    catalogue: pd.DataFrame,
    episode_meta: pd.DataFrame,
    in_scope_episode_urls: Set[str],
    ri_with_role: pd.DataFrame,
    top_n: Optional[int] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build guest × episode occurrence matrix.
    
    Args:
        catalogue: Person catalogue
        episode_meta: Episode metadata
        in_scope_episode_urls: Set of in-scope episode URLs
        ri_with_role: Reconciled guest-episode pairs with roles
        top_n: Optional; if set, return only top N guests by appearance count
        
    Returns:
        Tuple of (occurrence_matrix_df, occurrence_matrix_numeric)
    """
    # Guest subset
    guest_cat = catalogue[catalogue["role"] == "guest"].copy()
    
    # Guest-episode pairs
    guest_ceids = set(guest_cat["canonical_entity_id"])
    guest_pairs = ri_with_role[
        ri_with_role["canonical_entity_id"].isin(guest_ceids) &
        (ri_with_role["role"] == "guest")
    ][["canonical_entity_id", "fernsehserien_de_id"]].drop_duplicates()
    
    # Episode sort order (by premiere_date asc)
    ep_order = (
        episode_meta[episode_meta["episode_url"].isin(in_scope_episode_urls)]
        [["episode_url", "premiere_date", "fernsehserien_de_id", "program_name"]]
        .drop_duplicates("episode_url")
        .sort_values("premiere_date")
    )
    
    # Person sort order (appearance_count desc, then alpha)
    person_order = (
        guest_cat[["canonical_entity_id", "canonical_label", "appearance_count"]]
        .sort_values(["appearance_count", "canonical_label"], ascending=[False, True])
    )
    
    # Apply top_n filter if requested
    if top_n:
        person_order = person_order.head(top_n)
    
    # Pivot to matrix (1 = appeared, 0 = absent)
    guest_pairs["_val"] = 1
    matrix_num = guest_pairs.pivot_table(
        index="canonical_entity_id", columns="fernsehserien_de_id",
        values="_val", aggfunc="max", fill_value=0
    )
    
    ordered_persons = [c for c in person_order["canonical_entity_id"] if c in matrix_num.index]
    ordered_episodes = list(ep_order["episode_url"])
    matrix_num = matrix_num.reindex(index=ordered_persons, columns=ordered_episodes, fill_value=0)
    
    # Output format: 1/empty cells
    matrix_out = matrix_num.copy().astype(object)
    matrix_out[matrix_num == 0] = ""
    ceid_to_label = person_order.set_index("canonical_entity_id")["canonical_label"]
    matrix_out.insert(0, "canonical_label", ceid_to_label)
    matrix_out = matrix_out.reset_index()
    
    return matrix_out, matrix_num


def build_cooccurrence_matrix(
    occurrence_matrix_numeric: pd.DataFrame,
    top_n: int = 200,
) -> pd.DataFrame:
    """
    Build co-occurrence matrix (same-episode co-appearance) for top guests.
    
    Args:
        occurrence_matrix_numeric: Numeric occurrence matrix
        top_n: Number of top guests to include
        
    Returns:
        Co-occurrence matrix DataFrame
    """
    top_guests = occurrence_matrix_numeric.index[:top_n]
    top_num = occurrence_matrix_numeric.reindex(top_guests).fillna(0).astype(int)
    co_occ = top_num.dot(top_num.T)
    co_occ_out = co_occ.reset_index()
    return co_occ_out

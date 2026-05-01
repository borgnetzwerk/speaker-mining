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
    reconciled: pd.DataFrame,
    episode_guests_raw: pd.DataFrame,
    episode_meta: pd.DataFrame,
    in_scope_show_ids: Set[str],
    core_persons: Dict,
    qid_label: Dict[str, str],
    moderator_qids: Optional[Set[str]] = None,
    repo_root: Optional[Path] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Build person catalogue with role classification, appearance counts, and Wikidata properties.
    
    Args:
        dedup_persons: Entity deduplication results
        cluster_members: Cluster membership records
        reconciled: Reconciled person-episode matches
        episode_guests_raw: Raw episode guest data
        episode_meta: Episode metadata
        in_scope_show_ids: Set of show IDs to include in analysis
        core_persons: Archive Wikidata entity cache (QID → entity doc)
        qid_label: QID → human-readable label mapping
        moderator_qids: Optional set of known moderator QIDs
        
    Returns:
        Tuple of (catalogue, unmatched, unclassified) DataFrames
    """
    if moderator_qids is None:
        moderator_qids = set()
    
    # Define role priority: lower = higher priority in final assignment
    ROLE_MAP = {
        "Gast": "guest",
        "Kommentar": "guest",
        "Kommentator": "guest",
        "": "guest",  # empty = unspecified role
        "Moderation": "moderator",
        "Produktionsauftrag": "staff",
        "Produktionsfirma": "staff",
        "Redaktion": "staff",
        "Regie": "staff",
        "Drehbuch": "staff",
    }
    ROLE_PRIORITY = {"guest": 0, "moderator": 1, "staff": 2, "incidental": 3}
    
    # In-scope episode URLs
    in_scope_episode_urls = set(
        episode_meta[episode_meta["fernsehserien_de_id"].isin(in_scope_show_ids)]["episode_url"]
    )
    
    # Join reconciled → cluster_members to get canonical_entity_id
    cm_bridge = cluster_members[["alignment_unit_id", "canonical_entity_id"]].drop_duplicates("alignment_unit_id")
    reconciled_ceid = reconciled.merge(cm_bridge, on="alignment_unit_id", how="left")
    
    # Filter to in-scope episodes
    reconciled_inscope = reconciled_ceid[
        reconciled_ceid["fernsehserien_de_id"].isin(in_scope_episode_urls)
    ].copy()
    
    # Join with episode_guests_raw to get guest_role
    eg_lookup = (
        episode_guests_raw[["episode_url", "guest_name", "guest_role"]]
        .copy()
        .assign(_name_lower=lambda d: d["guest_name"].str.strip().str.lower())
    )
    reconciled_inscope["_name_lower"] = reconciled_inscope["canonical_label"].str.strip().str.lower()
    
    ri_with_role = reconciled_inscope.merge(
        eg_lookup.rename(columns={"episode_url": "fernsehserien_de_id", "guest_role": "raw_role"}),
        on=["fernsehserien_de_id", "_name_lower"],
        how="left"
    ).drop(columns=["_name_lower", "guest_name"], errors="ignore")
    
    ri_with_role["raw_role"] = ri_with_role["raw_role"].fillna("")
    ri_with_role["role"] = ri_with_role["raw_role"].map(ROLE_MAP).fillna("guest")
    ri_with_role.loc[ri_with_role["wikidata_id"].isin(moderator_qids), "role"] = "moderator"
    
    # Appearance count per canonical entity
    app_counts_s = (
        ri_with_role[ri_with_role["canonical_entity_id"].notna()]
        .groupby("canonical_entity_id")["fernsehserien_de_id"]
        .nunique()
        .rename("appearance_count")
        .reset_index()
    )
    
    # Dominant role per canonical entity (guest > moderator > staff > incidental)
    dominant_role_s = (
        ri_with_role[ri_with_role["canonical_entity_id"].notna()]
        .groupby("canonical_entity_id")["role"]
        .agg(lambda roles: min(roles, key=lambda r: ROLE_PRIORITY.get(r, 9)))
        .rename("role")
        .reset_index()
    )
    
    # Best wikidata_id per canonical entity from reconciled data
    TIER_ORDER = {"high": 0, "medium": 1, "low": 2, "": 9}
    best_qid_df = (
        reconciled_ceid[
            reconciled_ceid["canonical_entity_id"].notna() &
            (reconciled_ceid["wikidata_id"] != "")
        ][["canonical_entity_id", "wikidata_id", "match_tier"]]
        .assign(_rank=lambda d: d["match_tier"].map(TIER_ORDER).fillna(9).astype(int))
        .sort_values(["canonical_entity_id", "_rank"])
        .groupby("canonical_entity_id", as_index=False)
        .first()[["canonical_entity_id", "wikidata_id"]]
        .rename(columns={"wikidata_id": "reconciled_wikidata_id"})
    )
    
    # Build catalogue from dedup_persons
    catalogue = dedup_persons[[
        "canonical_entity_id", "wikidata_id", "canonical_label",
        "cluster_size", "cluster_strategy", "cluster_confidence"
    ]].copy()
    
    catalogue = (
        catalogue
        .merge(dominant_role_s, on="canonical_entity_id", how="left")
        .merge(app_counts_s, on="canonical_entity_id", how="left")
        .merge(best_qid_df, on="canonical_entity_id", how="left")
    )
    catalogue["role"] = catalogue["role"].fillna("incidental")
    
    # Override with reconciled QID (more complete)
    catalogue["wikidata_id"] = (
        catalogue["reconciled_wikidata_id"]
        .where(catalogue["reconciled_wikidata_id"].notna() & (catalogue["reconciled_wikidata_id"] != ""),
               other=catalogue["wikidata_id"])
        .fillna("")
    )
    catalogue.drop(columns=["reconciled_wikidata_id"], inplace=True)
    catalogue.loc[catalogue["wikidata_id"].isin(moderator_qids), "role"] = "moderator"
    catalogue["appearance_count"] = catalogue["appearance_count"].fillna(0).astype(int)
    
    # Lazy import entity_access once; None if unavailable
    _get_cached = None
    if repo_root is not None:
        try:
            from process.candidate_generation.wikidata.entity_access import get_cached_entity_doc as _gc
            _get_cached = _gc
        except Exception:
            pass

    # Extract Wikidata properties: archive first, entity_access cache fallback
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
    
    # Separate catalogues
    unmatched = catalogue[catalogue["wikidata_id"] == ""]
    unclassified = catalogue[catalogue["appearance_count"] == 0]
    
    return catalogue, unmatched, unclassified


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
    ordered_episodes = [e for e in ep_order["episode_url"] if e in matrix_num.columns]
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

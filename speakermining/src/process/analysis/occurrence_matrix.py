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
    aligned_episodes: pd.DataFrame,
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
        aligned_episodes: Aligned episode universe from Phase 31 (aligned_episodes.csv).
        in_scope_show_ids: Set of FS show IDs (fernsehserien_de_id) to include.
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
    # Moderator and staff must win over guest when a person appears in multiple roles.
    # A show host who is ever a guest elsewhere still has "moderator" as their canonical role.
    role_priority = {"moderator": 0, "staff": 1, "guest": 2, "incidental": 3}

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

    # Map each cluster member to alignment_unit_id(s) using ALL available sources.
    #
    # No single source is authoritative for episode assignment.  ZDF Archive,
    # fernsehserien.de, and Wikidata are equal contributors.  Each source is
    # queried independently and the results are unioned.
    #
    # IMPORTANT: fernsehserien_de_id (the alignment-context URL) is NEVER used
    # for episode assignment.  That column originates from Phase-31 alignment
    # context and can be wrong for rows from
    # data/31_entity_disambiguation/manual/reconciled_data_summary.csv (a
    # manually curated file that will never be regenerated and carries stale
    # FS URLs for some persons).  reconciled_data_summary.csv is authoritative
    # for person identity only — not for episode assignment.
    _ae = aligned_episodes
    fs_url_to_auid = (
        _ae[_ae["fernsehserien_de_id"].astype(str).str.strip() != ""]
        .set_index("fernsehserien_de_id")["alignment_unit_id"]
        .to_dict()
    )

    _source_frames = []

    # Source: ZDF Archive — episode_id_zdf IS the alignment_unit_id
    if "episode_id_zdf" in member_df.columns:
        _zdf = member_df.copy()
        _zdf["episode_auid"] = _zdf["episode_id_zdf"].fillna("").astype(str).str.strip()
        _source_frames.append(_zdf[_zdf["episode_auid"] != ""])

    # Source: fernsehserien.de guest data — episode_url_fernsehserien_de → alignment_unit_id
    if "episode_url_fernsehserien_de" in member_df.columns:
        _fs = member_df.copy()
        _fs["episode_auid"] = (
            _fs["episode_url_fernsehserien_de"].fillna("").astype(str).map(fs_url_to_auid).fillna("")
        )
        _source_frames.append(_fs[_fs["episode_auid"].str.strip() != ""])

    if _source_frames:
        member_df = pd.concat(_source_frames, ignore_index=True)
        member_df["episode_auid"] = member_df["episode_auid"].astype(str).str.strip()
        # Deduplicate (person, episode) pairs from multi-source aggregation.
        # When the same person appears in the same episode via multiple sources,
        # keep the row whose role is most specific (lower priority = more specific).
        member_df = (
            member_df[member_df["canonical_entity_id"].notna()]
            .sort_values("role", key=lambda s: s.map(lambda r: role_priority.get(r, 9)))
            .drop_duplicates(subset=["canonical_entity_id", "episode_auid"])
            .reset_index(drop=True)
        )
    else:
        member_df["episode_auid"] = ""

    # Derive show_id from aligned_episodes — the ONLY reliable source for
    # which show an episode belongs to.  This overrides any show_id value
    # inherited from cluster_members, which may be stale.
    _auid_to_show_id = (
        _ae.set_index("alignment_unit_id")["fernsehserien_de_id_fernsehserien_de"]
        .astype(str).str.strip().to_dict()
    )
    member_df["show_id"] = (
        member_df["episode_auid"]
        .map(_auid_to_show_id)
        .fillna(member_df.get("show_id", pd.Series("", index=member_df.index)).fillna("").astype(str))
        .astype(str).str.strip()
    )

    # In-scope episodes: all alignment_unit_ids whose show is in in_scope_show_ids.
    in_scope_episode_ids = set(
        _ae[_ae["fernsehserien_de_id_fernsehserien_de"].astype(str).str.strip().isin(in_scope_show_ids)]
        ["alignment_unit_id"].astype(str).str.strip()
    )

    # Build canonical date map: alignment_unit_id → "YYYY-MM-DD"
    _auid_to_date: dict = {}
    for _, _ep in _ae.iterrows():
        _auid = str(_ep.get("alignment_unit_id", "")).strip()
        if not _auid:
            continue
        _d = str(_ep.get("premiere_date_date_fernsehserien_de", "")).strip()[:10]
        if not _d or _d == "nan":
            _pub = str(_ep.get("publikationsdatum_zdf", "")).strip()
            if _pub:
                _parts = _pub.split(".")
                if len(_parts) == 3:
                    _d = f"{_parts[2]}-{_parts[1]}-{_parts[0]}"
        if _d:
            _auid_to_date[_auid] = _d

    in_scope_members = member_df[member_df["episode_auid"].isin(in_scope_episode_ids)].copy()

    app_counts_s = (
        in_scope_members[in_scope_members["canonical_entity_id"].notna()]
        .groupby("canonical_entity_id")["episode_auid"]
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

    # TASK-F16: Assign data quality tier (1–4) based on source reconciliation depth.
    # Tier 1: Wikidata QID + at least one other source match (cluster_size > 1 + QID).
    #         Entry exists in ≥2 databases, at least one being Wikidata — highest confidence.
    # Tier 2: Wikidata QID but no other source match (cluster_size == 1 + QID).
    #         Wikidata-only; limited cross-validation.
    # Tier 3: No Wikidata QID but matched across 2+ non-Wikidata sources (ZDF + FS).
    # Tier 4: No Wikidata QID and single non-Wikidata source only.
    def _quality_tier(row: pd.Series) -> int:
        qid = str(row.get("wikidata_id", "")).strip()
        has_qid = bool(qid and qid.lower() not in ("", "nan"))
        try:
            cluster_size = int(row.get("cluster_size", 1))
        except (ValueError, TypeError):
            cluster_size = 1
        if has_qid:
            return 1 if cluster_size > 1 else 2
        return 3 if cluster_size > 1 else 4
    catalogue["data_quality_tier"] = catalogue.apply(_quality_tier, axis=1)

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
        "data_quality_tier",
        "gender", "gender_qid", "birthyear", "birthplace", "birthplace_qid",
        "occupations", "occupation_qids", "party", "party_qids", "employer", "employer_qids",
    ]
    catalogue = catalogue[CATALOGUE_COLS]

    unmatched = catalogue[catalogue["wikidata_id"] == ""]
    unclassified = catalogue[catalogue["appearance_count"] == 0]

    episode_appearances = in_scope_members[in_scope_members["canonical_entity_id"].notna()].copy()
    if not episode_appearances.empty:
        episode_appearances = episode_appearances.rename(columns={
            "episode_auid": "episode_id",
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
        episode_appearances["premiere_date"] = episode_appearances["episode_id"].map(_auid_to_date)
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
    aligned_episodes: pd.DataFrame,
    in_scope_episode_ids: Set[str],
    ri_with_role: pd.DataFrame,
    top_n: Optional[int] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build guest × episode occurrence matrix.

    Args:
        catalogue: Person catalogue
        aligned_episodes: Aligned episode universe from Phase 31.
        in_scope_episode_ids: Set of alignment_unit_id values for in-scope episodes.
        ri_with_role: Reconciled guest-episode pairs with roles (must have episode_auid column).
        top_n: Optional; if set, return only top N guests by appearance count

    Returns:
        Tuple of (occurrence_matrix_df, occurrence_matrix_numeric)
    """
    # Guest subset
    guest_cat = catalogue[catalogue["role"] == "guest"].copy()

    # Guest-episode pairs — pivot column is alignment_unit_id
    guest_ceids = set(guest_cat["canonical_entity_id"])
    _ep_col = "episode_auid" if "episode_auid" in ri_with_role.columns else "episode_id"
    guest_pairs = ri_with_role[
        ri_with_role["canonical_entity_id"].isin(guest_ceids) &
        (ri_with_role["role"] == "guest")
    ][["canonical_entity_id", _ep_col]].drop_duplicates().rename(columns={_ep_col: "episode_auid"})

    # Build canonical date per alignment_unit_id for episode sort order
    _auid_to_date: dict = {}
    for _, _ep in aligned_episodes.iterrows():
        _auid = str(_ep.get("alignment_unit_id", "")).strip()
        if not _auid:
            continue
        _d = str(_ep.get("premiere_date_date_fernsehserien_de", "")).strip()[:10]
        if not _d or _d == "nan":
            _pub = str(_ep.get("publikationsdatum_zdf", "")).strip()
            if _pub:
                _parts = _pub.split(".")
                if len(_parts) == 3:
                    _d = f"{_parts[2]}-{_parts[1]}-{_parts[0]}"
        if _d:
            _auid_to_date[_auid] = _d

    # Episode sort order (by canonical premiere_date asc)
    ep_order = (
        aligned_episodes[aligned_episodes["alignment_unit_id"].isin(in_scope_episode_ids)]
        [["alignment_unit_id", "fernsehserien_de_id_fernsehserien_de", "program_name_fernsehserien_de"]]
        .drop_duplicates("alignment_unit_id")
        .copy()
    )
    ep_order["premiere_date"] = ep_order["alignment_unit_id"].map(_auid_to_date).fillna("")
    ep_order = ep_order.sort_values("premiere_date")

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
        index="canonical_entity_id", columns="episode_auid",
        values="_val", aggfunc="max", fill_value=0
    )

    ordered_persons = [c for c in person_order["canonical_entity_id"] if c in matrix_num.index]
    ordered_episodes = list(ep_order["alignment_unit_id"])
    matrix_num = matrix_num.reindex(index=ordered_persons, columns=ordered_episodes, fill_value=0)

    # Output format: 1/empty cells
    matrix_out = matrix_num.copy().astype(object)
    matrix_out[matrix_num == 0] = ""
    ceid_to_label = person_order.set_index("canonical_entity_id")["canonical_label"]
    matrix_out.insert(0, "canonical_label", ceid_to_label)
    matrix_out = matrix_out.reset_index()

    return matrix_out, matrix_num


def build_role_occurrence_matrices(
    catalogue: pd.DataFrame,
    aligned_episodes: pd.DataFrame,
    in_scope_episode_ids: Set[str],
    ri_with_role: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    """Build separate occurrence matrices for moderator and staff roles.

    Returns a dict with keys 'moderator' and 'staff', each containing a
    (canonical_entity_id + canonical_label) × episode occurrence DataFrame
    with 1/empty cells, matching the format of the guest occurrence matrix.
    """
    _ep_col = "episode_auid" if "episode_auid" in ri_with_role.columns else "episode_id"

    _auid_to_date: dict = {}
    for _, _ep in aligned_episodes.iterrows():
        _auid = str(_ep.get("alignment_unit_id", "")).strip()
        if not _auid:
            continue
        _d = str(_ep.get("premiere_date_date_fernsehserien_de", "")).strip()[:10]
        if not _d or _d == "nan":
            _pub = str(_ep.get("publikationsdatum_zdf", "")).strip()
            if _pub:
                _parts = _pub.split(".")
                if len(_parts) == 3:
                    _d = f"{_parts[2]}-{_parts[1]}-{_parts[0]}"
        if _d:
            _auid_to_date[_auid] = _d

    ep_order = (
        aligned_episodes[aligned_episodes["alignment_unit_id"].isin(in_scope_episode_ids)]
        [["alignment_unit_id"]]
        .drop_duplicates("alignment_unit_id")
        .copy()
    )
    ep_order["premiere_date"] = ep_order["alignment_unit_id"].map(_auid_to_date).fillna("")
    ordered_episodes = list(ep_order.sort_values("premiere_date")["alignment_unit_id"])

    results: Dict[str, pd.DataFrame] = {}
    for role in ("moderator", "staff"):
        role_cat = catalogue[catalogue["role"] == role].copy()
        role_ceids = set(role_cat["canonical_entity_id"])
        pairs = ri_with_role[
            ri_with_role["canonical_entity_id"].isin(role_ceids) &
            (ri_with_role["role"] == role)
        ][["canonical_entity_id", _ep_col]].drop_duplicates().rename(columns={_ep_col: "episode_auid"})

        if pairs.empty:
            results[role] = pd.DataFrame(columns=["canonical_entity_id", "canonical_label"])
            continue

        pairs["_val"] = 1
        mat = pairs.pivot_table(
            index="canonical_entity_id", columns="episode_auid",
            values="_val", aggfunc="max", fill_value=0
        )
        person_order = (
            role_cat[["canonical_entity_id", "canonical_label", "appearance_count"]]
            .sort_values(["appearance_count", "canonical_label"], ascending=[False, True])
        )
        ordered_persons = [c for c in person_order["canonical_entity_id"] if c in mat.index]
        mat = mat.reindex(index=ordered_persons, columns=ordered_episodes, fill_value=0)
        mat_out = mat.copy().astype(object)
        mat_out[mat == 0] = ""
        ceid_to_label = person_order.set_index("canonical_entity_id")["canonical_label"]
        mat_out.insert(0, "canonical_label", ceid_to_label)
        results[role] = mat_out.reset_index()

    return results


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

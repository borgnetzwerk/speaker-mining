"""
Layer 1b: Property Data Extraction

Implements TASK-B03: Extract property values for all guests.
Responsibilities:
- Extract values for Item properties (P106 occupation, P102 party, etc.)
- Extract Point-in-time values (birth date)
- Extract Quantity values
- Extract String values
- Compute derived properties (Age per guest × episode)
- Route each value to its property type for downstream analysis

Requirements: REQ-P01–P06
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime


def load_property_catalog(properties_csv_path: Path) -> pd.DataFrame:
    """
    Load the analysis properties catalog.
    
    Args:
        properties_csv_path: Path to properties.csv
        
    Returns:
        DataFrame with columns: wikidata_id, label, type, enabled, notes
    """
    if not properties_csv_path.exists():
        raise FileNotFoundError(f"Properties catalog not found: {properties_csv_path}")
    
    props = pd.read_csv(properties_csv_path, dtype=str).fillna("")
    # Filter to enabled properties
    props = props[props["enabled"].fillna("0") != "0"]
    return props


def extract_item_values(
    guest_qid: str,
    property_pid: str,
    entity_doc: Optional[Dict],
    qid_label: Dict[str, str],
) -> List[Dict]:
    """
    Extract Item property values (e.g. P106 occupation, P102 party).
    
    Args:
        guest_qid: The guest's QID
        property_pid: Property ID (e.g. "P106")
        entity_doc: Wikidata entity document (or None)
        qid_label: QID → label mapping
        
    Returns:
        List of dicts: [{"value_qid": "...", "value_label": "...", "refs": ..., "qualifiers": ...}, ...]
    """
    if not entity_doc:
        return []
    
    claims = entity_doc.get("claims", {})
    if property_pid not in claims:
        return []
    
    values = []
    for stmt in claims[property_pid]:
        try:
            value_qid = stmt["mainsnak"]["datavalue"]["value"]["id"]
            value_label = qid_label.get(value_qid, value_qid)
            
            # Collect qualifiers for temporal inference / semantic context
            qualifiers = stmt.get("qualifiers", {})
            qualifier_pids = list(qualifiers.keys())
            
            # Reference PIDs
            references = stmt.get("references", [])
            ref_pids = []
            for ref in references:
                ref_pids.extend(ref.get("snaks", {}).keys())
            ref_pids = list(set(ref_pids))
            
            values.append({
                "value_qid": value_qid,
                "value_label": value_label,
                "qualifier_pids": "|".join(qualifier_pids),
                "reference_pids": "|".join(ref_pids),
                "rank": stmt.get("rank", "normal"),
            })
        except (KeyError, TypeError):
            pass
    
    return values


def extract_time_values(
    guest_qid: str,
    property_pid: str,
    entity_doc: Optional[Dict],
) -> Optional[str]:
    """
    Extract Point-in-time property value (e.g. P569 birth date).
    
    Args:
        guest_qid: The guest's QID
        property_pid: Property ID (e.g. "P569")
        entity_doc: Wikidata entity document (or None)
        
    Returns:
        ISO date string (or None)
    """
    if not entity_doc:
        return None
    
    claims = entity_doc.get("claims", {})
    if property_pid not in claims:
        return None
    
    try:
        # Use the first (preferred) statement
        stmt = claims[property_pid][0]
        time_str = stmt["mainsnak"]["datavalue"]["value"]["time"]
        # ISO 8601 format: ±YYYY-MM-DDThh:mm:ssZ
        # For our purposes, extract the date part
        return time_str.split("T")[0] if "T" in time_str else time_str
    except (KeyError, TypeError, IndexError):
        return None


def extract_quantity_values(
    guest_qid: str,
    property_pid: str,
    entity_doc: Optional[Dict],
) -> Optional[float]:
    """
    Extract Quantity property value (e.g. height, number of children).
    
    Args:
        guest_qid: The guest's QID
        property_pid: Property ID
        entity_doc: Wikidata entity document (or None)
        
    Returns:
        Numeric value (or None)
    """
    if not entity_doc:
        return None
    
    claims = entity_doc.get("claims", {})
    if property_pid not in claims:
        return None
    
    try:
        stmt = claims[property_pid][0]
        amount_str = stmt["mainsnak"]["datavalue"]["value"]["amount"]
        # Amount is a signed decimal string, e.g. "+175"
        return float(amount_str)
    except (KeyError, TypeError, IndexError, ValueError):
        return None


def extract_string_values(
    guest_qid: str,
    property_pid: str,
    entity_doc: Optional[Dict],
) -> Optional[str]:
    """
    Extract String property value.
    
    Args:
        guest_qid: The guest's QID
        property_pid: Property ID
        entity_doc: Wikidata entity document (or None)
        
    Returns:
        String value (or None)
    """
    if not entity_doc:
        return None
    
    claims = entity_doc.get("claims", {})
    if property_pid not in claims:
        return None
    
    try:
        stmt = claims[property_pid][0]
        return stmt["mainsnak"]["datavalue"]["value"]
    except (KeyError, TypeError, IndexError):
        return None


def compute_age(
    birth_year: Optional[str],
    episode_year: Optional[str],
) -> Optional[int]:
    """
    Compute appearance age from birth year and episode year.
    
    Args:
        birth_year: ISO date string (YYYY-MM-DD) or year string (YYYY)
        episode_year: Year string (YYYY)
        
    Returns:
        Age in years (or None if cannot compute)
    """
    if not birth_year or not episode_year:
        return None
    
    try:
        birth_yr = int(birth_year[:4])
        ep_yr = int(episode_year[:4])
        age = ep_yr - birth_yr
        if 0 <= age < 120:
            return age
    except (ValueError, TypeError):
        pass
    
    return None


def extract_all_properties(
    catalogue: pd.DataFrame,
    episode_appearances: pd.DataFrame,
    property_catalog: pd.DataFrame,
    core_persons: Dict,
    qid_label: Dict[str, str],
) -> Dict[str, pd.DataFrame]:
    """
    Extract all enabled properties for all guests.
    
    Args:
        catalogue: Person catalogue
        episode_appearances: Episode × person data
        property_catalog: Loaded properties catalog
        core_persons: Archive Wikidata entity cache
        qid_label: QID → label mapping
        
    Returns:
        Dict[property_pid → DataFrame with extracted values]
    """
    property_values_by_pid = {}
    
    for _, prop_row in property_catalog.iterrows():
        prop_pid = prop_row["wikidata_id"]
        prop_label = prop_row["label"]
        prop_type = prop_row["type"].strip()
        
        print(f"Extracting {prop_label} ({prop_pid}, type={prop_type})...")
        
        if prop_type == "Item":
            # Extract item values: for each guest, extract all values
            records = []
            for _, guest in catalogue.iterrows():
                qid = guest["wikidata_id"]
                if not qid:
                    continue
                
                entity = core_persons.get(qid)
                values = extract_item_values(qid, prop_pid, entity, qid_label)
                
                for val in values:
                    records.append({
                        "guest_qid": qid,
                        "guest_label": guest["canonical_label"],
                        **val,
                    })
            
            if records:
                property_values_by_pid[prop_pid] = pd.DataFrame(records)
            print(f"  → {len(records)} values extracted")
        
        elif prop_type == "Point_in_time":
            # Extract point-in-time values (typically birth date, death date)
            records = []
            for _, guest in catalogue.iterrows():
                qid = guest["wikidata_id"]
                if not qid:
                    continue
                
                entity = core_persons.get(qid)
                value = extract_time_values(qid, prop_pid, entity)
                
                if value:
                    records.append({
                        "guest_qid": qid,
                        "guest_label": guest["canonical_label"],
                        "value": value,
                        "value_year": value[:4],
                    })
            
            if records:
                property_values_by_pid[prop_pid] = pd.DataFrame(records)
            print(f"  → {len(records)} values extracted")
        
        elif prop_type == "Quantity":
            # Extract quantity values
            records = []
            for _, guest in catalogue.iterrows():
                qid = guest["wikidata_id"]
                if not qid:
                    continue
                
                entity = core_persons.get(qid)
                value = extract_quantity_values(qid, prop_pid, entity)
                
                if value is not None:
                    records.append({
                        "guest_qid": qid,
                        "guest_label": guest["canonical_label"],
                        "value": value,
                    })
            
            if records:
                property_values_by_pid[prop_pid] = pd.DataFrame(records)
            print(f"  → {len(records)} values extracted")
        
        elif prop_type == "String":
            # Extract string values
            records = []
            for _, guest in catalogue.iterrows():
                qid = guest["wikidata_id"]
                if not qid:
                    continue
                
                entity = core_persons.get(qid)
                value = extract_string_values(qid, prop_pid, entity)
                
                if value:
                    records.append({
                        "guest_qid": qid,
                        "guest_label": guest["canonical_label"],
                        "value": value,
                    })
            
            if records:
                property_values_by_pid[prop_pid] = pd.DataFrame(records)
            print(f"  → {len(records)} values extracted")
        
        elif prop_type == "Derived":
            # Computed properties (e.g. Age)
            if "age" in prop_label.lower():
                records = []
                for _, row in episode_appearances.iterrows():
                    age = compute_age(row.get("birthyear"), row.get("premiere_year"))
                    if age is not None:
                        records.append({
                            "guest_qid": row["wikidata_id"],
                            "episode_id": row["fernsehserien_de_id"],
                            "age": age,
                        })
                
                if records:
                    property_values_by_pid[prop_pid] = pd.DataFrame(records)
                print(f"  → {len(records)} values computed")
    
    return property_values_by_pid

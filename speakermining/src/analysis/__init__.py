"""Shared analysis helpers for the restructuring redesign."""

from .color_registry import ColorRegistry
from .config import (
    ANALYSIS_PROPERTIES_PATH,
    LOOP_RESOLUTION_PATH,
    MIDLEVEL_CLASSES_PATH,
    PARTY_COLORS_PATH,
    infer_temporal_properties_from_values,
    load_analysis_properties,
    load_loop_resolution,
    load_midlevel_classes,
    load_party_colors,
    normalize_analysis_properties,
)
from .occurrence_matrix import (
    build_person_catalogue,
    build_occurrence_matrix,
    build_cooccurrence_matrix,
    extract_wikidata_properties,
)
from .property_extraction import (
    load_property_catalog,
    extract_all_properties,
    extract_item_values,
    extract_time_values,
    extract_quantity_values,
    extract_string_values,
    compute_age,
)
from .universal_stats import (
    UNKNOWN_LABEL,
    compute_carrier_stats,
    compute_episode_appearance_stats,
    build_frequency_distribution,
    build_pareto_table,
)
from .viz_base import (
    PALETTE,
    apply_font,
    save_fig,
    sort_bars_descending,
    add_unknown_row,
    add_scope_label,
    add_context_stats,
    stacked_bar_from_zero,
    place_bar_labels,
    apply_other_grouping,
)
from .viz_universal import (
    universal_visualizations,
    make_universal_chart,
)

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
    build_role_occurrence_matrices,
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
    expand_property_values_to_appearances,
    build_value_episode_matrix,
    build_frequency_distribution,
    build_pareto_table,
    compute_value_combinations,
    compute_cross_property_combinations,
    add_dominance_ratio,
    build_property_type_summary,
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
from .viz_dashboards import (
    build_guest_frequency_pareto_outputs,
    build_source_coverage_dashboards,
)
from .readme_generator import generate_all_readmes
from .viz_cross_property import (
    build_cross_property_stacked_bars,
    build_property_top_persons_chart,
)
from .viz_comparison import (
    build_cross_show_comparison,
    build_all_cross_show_comparisons,
)
from .viz_coverage import build_property_coverage_dashboard
from .viz_scalar import (
    build_birth_year_chart,
    build_age_distribution_chart,
    build_age_vs_appearances_scatter,
    build_all_scalar_charts,
)
from .viz_treemap import (
    build_property_treemap,
    build_all_treemaps,
)
from .viz_radar import (
    build_property_radar_chart,
    build_all_radar_charts,
)
from .viz_persons import (
    build_cooccurrence_heatmap,
    build_relevance_chart,
)
from .viz_binary import (
    build_all_binary_presence,
    build_binary_presence_chart,
    compute_binary_presence,
)
from .person_analysis import (
    compute_top_guests_by_show,
    compute_person_relevance,
)

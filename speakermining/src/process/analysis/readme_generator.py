"""Auto-generate GitHub-navigable README.md files for analysis output folders.

For each output scope (all/ and per-show directories), writes a README.md that
embeds PNG visualizations inline and includes summary tables so GitHub folder
navigation alone reveals the key findings — no file-clicking required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


REQUIRED_PER_SHOW_COLUMNS = {
    "show_id",
    "program_name",
    "episode_count",
    "guest_appearances",
    "unique_guests",
    "avg_guests_per_episode",
}


def _validate_per_show_stats(per_show_stats: pd.DataFrame) -> None:
    if per_show_stats is None:
        raise ValueError("per_show_stats must not be None")
    missing = REQUIRED_PER_SHOW_COLUMNS.difference(per_show_stats.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"per_show_stats missing required columns: {missing_cols}")


def _md_table(df: pd.DataFrame, max_rows: int = 10) -> str:
    """Render a DataFrame as a Markdown table (first max_rows rows)."""
    subset = df.head(max_rows)
    if subset.empty:
        return "_No data available._"
    cols = list(subset.columns)
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    rows = []
    for _, row in subset.iterrows():
        cells = []
        for c in cols:
            val = row[c]
            if isinstance(val, float):
                cells.append(f"{val:,.1f}")
            elif isinstance(val, int):
                cells.append(f"{val:,}")
            else:
                cells.append(str(val))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, sep] + rows)


def _embed_png(path: Path, rel_base: Path, caption: str = "") -> str:
    """Return a Markdown image tag using a path relative to rel_base, or empty string if missing."""
    if not path.exists():
        return ""
    try:
        rel = path.relative_to(rel_base)
    except ValueError:
        rel = path
    img = f"![{caption}]({rel.as_posix()})"
    return f"{img}\n\n*{caption}*\n" if caption else f"{img}\n"


def generate_all_readme(
    all_dir: Path,
    per_show_stats: pd.DataFrame,
    *,
    top_guests_combined: Optional[pd.DataFrame] = None,
    analysis_summary: Optional[dict] = None,
    property_viz_names: Optional[list[str]] = None,
) -> None:
    """Generate README.md for the all/ combined output folder."""
    _validate_per_show_stats(per_show_stats)
    viz_dir = all_dir / "visualizations"
    lines: list[str] = []

    # Header
    lines.append("# Speaker Mining — Combined Analysis\n")
    lines.append("*Auto-generated. Navigate sub-folders for per-show details.*\n")
    lines.append("")

    # Summary stats
    total_eps = int(per_show_stats["episode_count"].sum()) if not per_show_stats.empty else "?"
    total_guests = int(per_show_stats["unique_guests"].sum()) if not per_show_stats.empty else "?"
    total_appearances = int(per_show_stats["guest_appearances"].sum()) if not per_show_stats.empty else "?"
    n_shows = len(per_show_stats) if not per_show_stats.empty else "?"

    if analysis_summary:
        total_eps = analysis_summary.get("total_episodes_analyzed", total_eps)
        total_guests = analysis_summary.get("total_unique_guests", total_guests)
        total_appearances = analysis_summary.get("total_guest_appearances", total_appearances)

    lines.append("## Summary\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"| --- | --- |")
    lines.append(f"| Broadcasting programs | {n_shows:,} |")
    lines.append(f"| Episodes analyzed | {total_eps:,} |")
    lines.append(f"| Unique guests | {total_guests:,} |")
    lines.append(f"| Total guest appearances | {total_appearances:,} |")
    lines.append("")

    # Per-show breakdown
    lines.append("## Broadcasting Programs\n")
    if not per_show_stats.empty:
        display_cols = [c for c in ["program_name", "show_id", "episode_count", "guest_appearances", "unique_guests", "avg_guests_per_episode"] if c in per_show_stats.columns]
        lines.append(_md_table(per_show_stats[display_cols].sort_values("guest_appearances", ascending=False)))
    lines.append("")

    # Pareto and stacked pareto visualizations
    pareto_png = viz_dir / "guest_frequency_pareto.png"
    stacked_png = viz_dir / "guest_frequency_stacked.png"
    pareto_section_opened = False
    for path, caption in [
        (stacked_png, "Top guests by appearances — stacked by broadcasting program (horizontal)"),
        (pareto_png, "Top guests by appearances — cumulative Pareto"),
    ]:
        img = _embed_png(path, all_dir, caption)
        if img:
            if not pareto_section_opened:
                lines.append("## Top Guests by Appearances\n")
                pareto_section_opened = True
            lines.append(img)

    # Top guests table
    if top_guests_combined is not None and not top_guests_combined.empty:
        if not pareto_section_opened:
            lines.append("## Top Guests by Appearances\n")
        lines.append("### Top 10 Guests (All Shows Combined)\n")
        id_col = "canonical_entity_id" if "canonical_entity_id" in top_guests_combined.columns else None
        display_cols = [c for c in ["canonical_label", "wikidata_id", "appearance_count"] if c in top_guests_combined.columns]
        top10 = (
            top_guests_combined
            .sort_values("appearance_count", ascending=False)
            .drop_duplicates(subset=[id_col] if id_col else display_cols[:1])
            .head(10)
        )
        lines.append(_md_table(top10[display_cols]))
        lines.append("")

    # Property visualizations
    lines.append("## Property Distributions\n")
    priority_props = [
        ("universal_P21_sex_or_gender.png", "sex or gender"),
        ("universal_P106_occupation.png", "occupation (top 20)"),
        ("universal_P27_country_of_citizenship.png", "country of citizenship"),
        ("universal_P102_member_of_political_party.png", "member of political party"),
        ("universal_P512_academic_degree.png", "academic degree"),
        ("universal_AGE_age.png", "age distribution"),
    ]
    for fname, caption in priority_props:
        img = _embed_png(viz_dir / fname, all_dir, caption)
        if img:
            lines.append(img)

    # Source coverage
    src_overall = viz_dir / "source_coverage" / "coverage_overall.png"
    src_stacked = viz_dir / "source_coverage" / "coverage_by_show_stacked.png"
    src_cmp = viz_dir / "source_coverage" / "coverage_comparison_by_show.png"
    src_imgs = []
    for path, caption in [
        (src_overall, "overall Wikidata reconciliation coverage"),
        (src_stacked, "coverage by show (stacked)"),
        (src_cmp, "cross-show coverage comparison"),
    ]:
        img = _embed_png(path, all_dir, caption)
        if img:
            src_imgs.append(img)
    if src_imgs:
        lines.append("## Source Coverage\n")
        lines.extend(src_imgs)

    readme_path = all_dir / "README.md"
    readme_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Written: {readme_path.relative_to(all_dir.parent.parent)}")


def generate_show_readme(
    show_dir: Path,
    *,
    show_id: str,
    program_name: str,
    episode_count: int,
    guest_appearances: int,
    unique_guests: int,
    avg_guests_per_episode: float = 0.0,
    top_guests: Optional[pd.DataFrame] = None,
) -> None:
    """Generate README.md for a per-show output folder."""
    lines: list[str] = []

    lines.append(f"# {program_name}\n")
    lines.append("*Auto-generated. See [combined analysis](../all/README.md) for cross-show comparisons.*\n")
    lines.append("")
    lines.append("## Show Statistics\n")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Show ID | `{show_id}` |")
    lines.append(f"| Episodes | {episode_count:,} |")
    lines.append(f"| Guest appearances | {guest_appearances:,} |")
    lines.append(f"| Unique guests | {unique_guests:,} |")
    if avg_guests_per_episode:
        lines.append(f"| Avg guests per episode | {avg_guests_per_episode:.2f} |")
    lines.append("")

    if top_guests is not None and not top_guests.empty:
        lines.append("## Top Guests\n")
        display_cols = [c for c in ["rank", "canonical_label", "wikidata_id", "appearance_count"] if c in top_guests.columns]
        lines.append(_md_table(top_guests[display_cols], max_rows=25))
        lines.append("")

    readme_path = show_dir / "README.md"
    readme_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Written: {readme_path.name} ({show_id})")


def generate_all_readmes(
    output_dir: Path,
    per_show_stats: pd.DataFrame,
    top_guests_by_show: dict[str, pd.DataFrame],
    *,
    top_guests_combined: Optional[pd.DataFrame] = None,
    analysis_summary: Optional[dict] = None,
) -> None:
    """Generate README.md files for all/ and all per-show output directories."""
    _validate_per_show_stats(per_show_stats)
    all_dir = output_dir / "all"
    if all_dir.exists():
        generate_all_readme(
            all_dir,
            per_show_stats,
            top_guests_combined=top_guests_combined,
            analysis_summary=analysis_summary,
        )

    if per_show_stats.empty:
        return

    for _, row in per_show_stats.iterrows():
        show_id = str(row.get("show_id", "")).strip()
        if not show_id:
            continue
        show_dir = output_dir / show_id.replace("-", "_")
        if not show_dir.exists():
            continue
        top_guests = top_guests_by_show.get(show_id)
        generate_show_readme(
            show_dir,
            show_id=show_id,
            program_name=str(row.get("program_name", show_id)),
            episode_count=int(row.get("episode_count", 0)),
            guest_appearances=int(row.get("guest_appearances", 0)),
            unique_guests=int(row.get("unique_guests", 0)),
            avg_guests_per_episode=float(row.get("avg_guests_per_episode", 0.0)),
            top_guests=top_guests,
        )

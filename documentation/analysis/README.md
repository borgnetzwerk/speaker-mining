# Analysis Phase Documentation

This folder documents the design, principles, and active tasks for the statistical analysis phase (Phase 5) of the speaker-mining pipeline.

## What This Phase Does

Phase 5 takes the deduplicated, reconciled guest catalogue and produces statistical analyses and visualizations of broadcasting program demographics. It answers questions such as: How has the gender distribution of talk show guests changed over time? What is the occupation breakdown by show? Which guests appear most frequently?

## Governing Principles

Phase 5 follows all repository coding principles:
- `documentation/coding-principles.md` — notebook orchestration, module boundaries, event-sourcing, file-write resilience
- `documentation/Wikidata/Wikidata.md` — when accessing cached Wikidata properties

## Building Blocks

### Broadcasting Program (Talk Show / Podcast)

The set of relevant broadcasting programs is defined in `data/00_setup/broadcasting_programs.csv`. Every analysis runs in two modes:
- Across all broadcasting programs combined
- For each specific broadcasting program individually

Every analysis, visualization, and README that is created for "ALL" must also be created per show — and vice versa.

### Episode

Episodes are the fundamental knowledge clusters. Key properties:
- Belong to a broadcasting program
- Have a release date (earliest publication date across sources)
- Link to guests

### Guest (Person)

Approximately 5,000–9,000 unique guests in the dataset, depending on pipeline completion. Guests are identified as such only in relation to an episode of a relevant broadcasting program. Not every human entity in the dataset is a guest — role classification matters.

Guest classification (per episode): `guest`, `moderator`, `staff`. Only guests enter property statistics and visualizations.

### Quality Tiers

Every person in the catalogue is classified into one of four quality tiers based on source reconciliation depth:

| Tier | Definition |
|---|---|
| 1 | Wikidata QID + cross-source match (ZDF, FS, or other) — full property coverage possible |
| 2 | Wikidata QID without cross-source match — limited properties available |
| 3 | No Wikidata QID but matched across multiple non-Wikidata sources |
| 4 | No Wikidata QID and single-source only |

Only Tiers 1 and 2 are used in property statistics and visualizations. All four tiers appear in summary counts.

## Key Properties Analyzed

| Property | Notes |
|---|---|
| Age | Derived per appearance: episode release date minus guest birth date |
| Gender (P21) | Set of possible options, not binary |
| Occupation (P106) | Clustered by P279 subclass hierarchy |
| Party affiliation (P102) | Time-qualified where possible |
| Employer (P108) | Time-qualified where possible |

Every time-qualified property (party, employer, position) should be evaluated against the episode's broadcast date. Temporal qualifiers (start/end time) are preserved in the event store.

## Analysis Symmetry Principles

**Guest ↔ Appearance symmetry:** Every visualization from a "by unique guest" perspective must also exist from a "by appearance" (guest × episode pair) perspective.

**ALL ↔ Per-Show symmetry:** Every analysis or chart produced for all shows combined must also be produced per show, and vice versa.

**Property-driven automation:** Analysis routing is driven by `data/00_setup/analysis_properties.csv` — adding a property to that file should automatically include it in all applicable analysis paths without notebook edits.

## Module Structure

| Component | Location |
|---|---|
| Orchestrating notebook | `speakermining/src/process/notebooks/50_analysis.ipynb` |
| Analysis modules root | `speakermining/src/process/analysis/` |
| Visualization modules | `speakermining/src/process/analysis/viz_*.py` |
| README generator | `speakermining/src/process/analysis/readme_generator.py` |
| Output root | `data/50_analysis/` |

The notebook orchestrates; all computation lives in `process.analysis` modules.

## Output Structure

```
data/50_analysis/
├── all/                    ← Combined analysis across all shows
│   ├── README.md           ← Auto-generated from analysis outputs
│   ├── carrier_stats.csv
│   ├── top_guests*.csv
│   ├── property_type_summary.csv
│   ├── person_quality_tiers.csv
│   └── visualizations/
│       └── *.png
├── <show_id>/              ← Per-show analysis (one folder per show)
│   ├── README.md           ← Auto-generated
│   └── ...
└── .gitignore              ← Excludes GDPR-sensitive and oversized files
```

## GitHub Publication Policy

Files in `data/50_analysis/` are selectively tracked via `.gitignore`:
- **Included:** PNG visualizations, aggregate summary CSVs, `README.md` files
- **Excluded:** per-person profiles (`persons/`), occurrence matrices, PDF/HTML chart variants

## Related Documentation

- [visualization-design.md](visualization-design.md) — Design principles and module boundary contract for visualization modules
- `documentation/findings.md` — Data quality findings relevant to analysis
- `documentation/data_reference.md` — Verified pipeline output numbers

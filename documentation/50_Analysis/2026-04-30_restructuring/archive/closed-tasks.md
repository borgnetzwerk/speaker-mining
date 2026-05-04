
## TASK-B19 — Setup Config Files for Human Specification

**Priority:** Immediate — prerequisite for TASK-B01, TASK-B04, TASK-B14  
**Status:** Completed  
**Requirements:** REQ-C01, REQ-H04, REQ-H06, REQ-V03

Create the following configuration files in `data/00_setup/`, following the existing CSV pattern (see `core_classes.csv`, `properties.csv` for format reference):

1. **`loop_resolution.csv`** — columns: `loop_member_qid, loop_member_label, designated_top_level_qid, designated_top_level_label, note`  
   Seed with the scientist (Q901) / researcher (Q1650915) / academic professional (Q66666685) / academic (Q3400985) loop; designated top-level = academic (Q3400985).
2. **`midlevel_classes.csv`** — columns: `wikidata_id, label, note`  
   Seed with: Q901 (scientist), Q37226 (teacher), Q135106813 (musical occupation), Q58635633 (media profession), Q12737077 (occupation).
3. **`party_colors.csv`** — columns: `wikidata_id, label, hex_color`  
   Seed with at minimum: CDU (Q49762), SPD (Q49763), Greens (Q49764), FDP (Q49802) and other major German parties present in the dataset.

All files must be human-editable without code changes. Code reads from them on every run.

---

## TASK-B01 — Color Registry

**Priority:** Immediate — prerequisite for all visualization tasks  
**Status:** Completed  
**Requirements:** REQ-V01, REQ-V02, REQ-V03, REQ-I09  
**Depends on:** TASK-B19

Implement a global color registry module. Responsibilities:
1. Seed known party colors from `data/00_setup/party_colors.csv`
2. Assign colors deterministically from a palette for all other QIDs, ensuring uniqueness within a diagram
3. Maintain global consistency: once a QID is assigned a color, it retains that color across all diagrams
4. Expose a single lookup function: `get_color(qid_or_label) → hex`

---

## TASK-B25 — Define Extended Color Palette and Update Visualization Principles

**Priority:** Immediate — prerequisite for TASK-B01  
**Status:** Completed  
**Requirements:** REQ-V01, REQ-V02, REQ-V03, REQ-V14  
**Depends on:** TASK-B19

Define the extended color palette used by the color registry (REQ-V14). The Okabe-Ito 8 colors are the seed set; this task extends them to 12–16 total colorblind-safe colors so that visualizations with 10+ distinct entities have a larger range before wrapping occurs.
   * **Clarification:** We must be able to do this automatically. When Okabe-Ito only has 8 colors and we need 16, then use Redundant Encoding: Don't rely solely on color. Add different filling or line types (dashed, dotted, solid), ensuring they remain clear in grayscale.

1. Confirm the two reserved colors (`#999999` for Unknown, `#CCCCCC` for Other) are not included in the palette; if any clash exists, adjust the reserved shades
2. Implement palette collision avoidance in `color_registry.py`: after seeding known party colors, remove any palette entries whose hex matches an already-seeded hex before dynamic assignment
   * **Clarification:** The parties don't have a monopoly on their colors. It is fine if an occupation shares the same color as a political party.
3. Update `documentation/visualizations/visualization-principles.md`: add the extended palette entries; document the Unknown/Other color distinction; document the collision-avoidance rule

---
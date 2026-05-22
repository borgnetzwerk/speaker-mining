# T10c: Verify V3 Architecture Diagrams Are Still Accurate

`documentation/visualizations/` contains 4 drawio diagrams (PDF + PNG):
- `SpeakerMining_V3-Approach.drawio.*` — embedded in `README.md` and `documentation/workflow.md`
- `SpeakerMining_V3-P1.drawio.*` — Phase 1 detail
- `SpeakerMining_V3-P2.drawio.*` — Phase 2 detail
- `SpeakerMining_V3-P3.drawio.*` — Phase 3 detail

Added in commit `3fccaf8` (March 2026). Pipeline has evolved since.

## Action

Open each PNG and verify it matches the current pipeline:
- Does the Approach diagram still correctly describe the end-to-end flow?
- Are P1/P2/P3 diagrams referenced anywhere? (Currently: only Approach is embedded)

If accurate: no action needed.
If stale: update the `.drawio.xml` source (gitignored — edit locally), re-export PNG/PDF, commit.

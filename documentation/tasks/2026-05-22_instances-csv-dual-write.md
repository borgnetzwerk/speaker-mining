# instances-csv-dual-write

* priority: medium
* scope: architecture
* legacy-id: TODO-034

## Summary

`_materialize` writes `instances.csv` (materializer format, `id` column, 36,890 rows) at line 2419, then `run_handlers` overwrites it with InstancesHandler format (`qid` column, 20,836 rows). The parquet sidecar is the reliable comprehensive source. `instances.csv` should be exclusively owned by InstancesHandler.

## Evidence

`materializer.py` line 2419 (`_write_tabular_artifact(paths.instances_csv, instances_df)`); `handlers/instances_handler.py` `materialize()`. `instances.parquet` (36,890 rows) vs `instances.csv` (20,836 rows, qid/label/labels_de columns).

## Definition of done

1. `_materialize` no longer writes to `paths.instances_csv`; it writes to a separate file (e.g. `instances_materialized.csv`) or relies solely on the parquet sidecar.
2. All consumers that need the comprehensive entity view (e.g. Notebook 41's `qid_label` lookup) read from `instances.parquet` or the renamed file.
3. `contracts.md` is updated to document which file is owned by which component.

## Notes

The current state is functional — Notebook 41's `qid_label` resolves all occupation labels correctly via the 20,836 entities in the handler file. The 16,054-row gap is entities added through node-store paths rather than entity_fetch events. Fix before the next time the label lookup breaks.

# Archive

Historical material from building and verifying the fact sheet pipeline. **Nothing here is needed to run the pipeline**, and the pipeline does not use any of it. It's kept as a record of how the numbers were checked.

## `reports/`

Verification and implementation notes written during development (March 2026):

| File | What it is |
|------|------------|
| `data_verification_report.md` | Fact sheet values checked against official published sources |
| `data_verification_summary.md` | One-page summary of the above |
| `data_comparison_table.md` | Side-by-side table: our values vs. official sources |
| `VALIDATION_REPORT.md` | Recalculation check of every fact sheet metric from the raw datasets |
| `VALIDATION_SUMMARY.md` | Summary of the above |
| `NIBRS_IMPLEMENTATION.md` | Notes on adding the NIBRS crime data and the 2022–2024 overlap with the older SRS data |

Some numbers in these reports predate later data updates.

## `scripts/`

One-off scripts used during development. Run them from the repository root, e.g. `PYTHONPATH=. python3 archive/scripts/validate_factsheet.py`.

| File | What it did |
|------|-------------|
| `validate_factsheet.py` | Recomputes metrics from the datasets to cross-check the fact sheet |
| `regenerate_factsheet_from_existing.py` | Rebuilt the fact sheet from already-downloaded data when the Census API was timing out |
| `check_msde_download.py` | Manual check that live MSDE Report Card downloads work (downloads real data; not part of `pytest`) |
| `recompute_crime_only.py` | Re-pulled crime data after a classification fix |
| `extend_to_present.py` | ⚠️ **Estimates** population for years Census hasn't published yet. Its output is a projection, not official data. Don't use it for anything you'll present as fact. |

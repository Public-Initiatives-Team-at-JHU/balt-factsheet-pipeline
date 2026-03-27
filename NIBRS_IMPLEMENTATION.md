# NIBRS Implementation Summary

**Date:** 2026-03-20
**Implemented:** Option 2 (Dual Reporting Period with 2022-2024 Overlap)

## What Was Implemented

### 1. **NIBRS Pipeline Module** (`src/pipelines/nibrs.py`)
New API client for NIBRS Group A crime data from Open Baltimore:
- Fetches from ArcGIS FeatureServer (2022-present)
- Classifies crimes as violent/property/other
- Maps NIBRS crime types to Part 1 equivalents
- Dataset covers: 2022-01-01 through present (updated weekly)

**Key differences from SRS:**
- NIBRS eliminates hierarchy rule → ~10.6% higher counts
- Separates larceny into 4 subtypes (LARCENY, LARCENY FROM AUTO, LARCENY OF MV PARTS, SHOPLIFTING)
- Includes additional Group A offenses not in Part 1 (excluded from Part 1 rate)

### 2. **NIBRS Dataset Definitions** (`src/pipelines/datasets.py`)
Added:
- `NIBRSDataset` dataclass (parallel to `OpenBaltimoreDataset`)
- `pull_and_clean_nibrs_dataset()` function
- `CRIME_NIBRS_GROUPA` dataset definition
- Updated `CRIME_PART1` title to "BPD Part 1 Crime (SRS)" for clarity

### 3. **NIBRS Metrics** (`src/pipelines/metrics.py`)
Added 4 new metrics (all with `[NIBRS]` suffix in name):
- `groupa_crime_rate_per_1k_nibrs` — Part 1 Crime Rate (per 1,000) [NIBRS]
- `violent_crime_rate_per_1k_nibrs` — Violent Crime Rate (per 1,000) [NIBRS]
- `property_crime_rate_per_1k_nibrs` — Property Crime Rate (per 1,000) [NIBRS]
- `homicide_count_nibrs` — Homicides (count) [NIBRS]

These parallel the existing SRS metrics and use the same rate calculation (count / ACS population × 1,000).

### 4. **Updated Pipeline Runner** (`src/run_factsheet.py`)
- Pulls both SRS and NIBRS datasets
- Computes rates for both using ACS population denominators
- Saves separate datasets: `ob_crime_rates` (SRS) and `nibrs_crime_rates` (NIBRS)

### 5. **Dual-Line Visualizations** (`scripts/plot_factsheet.py`)
Crime plots now show:
- **Blue solid line** — SRS (legacy, 2012-2024)
- **Orange dashed line** — NIBRS (current, 2022-present)
- **Legend** — Distinguishes SRS vs NIBRS
- **Vertical line at 2024.5** — Marks methodology change
- **Dual source annotation** — "SRS: ... | NIBRS: ..."

For non-crime metrics, plots remain single-line as before.

### 6. **Configuration Updates** (`src/utils/config.py`)
- Updated `ACS1_LATEST_YEAR = 2024` (from 2023)
- Updated `ACS_LATEST_YEAR = 2024` (from 2023)
- Added `SRS_START_YEAR`, `SRS_END_YEAR`, `NIBRS_START_YEAR` constants

---

## Data Coverage

### ACS Data
- **2024 data** available (released Sept 2025)
- **2025-2026 population estimates** extrapolated using 2020-2024 linear trend
- All ACS tables through 2024 (official); 2025-2026 (estimated)

### Crime Data
| Dataset | Years | Methodology | Source |
|---------|-------|-------------|--------|
| **SRS (legacy)** | 2012–2024 | FBI UCR Summary Reporting System | Part1_Crime_Beta FeatureServer |
| **NIBRS (current)** | 2022–2026 | FBI NIBRS Group A | NIBRS_GroupA_Crime_Data FeatureServer |
| **Overlap period** | 2022–2024 | Both SRS and NIBRS available | Allows methodology comparison |

**Note:** 2026 data is partial (Jan-Mar only, as of 2026-03-20)

---

## Output Files

### Datasets (`data/datasets/`)
- `ob_crime_part1.csv` — SRS crime counts by year
- `nibrs_groupa.csv` — NIBRS crime counts by year
- `ob_crime_rates.csv` — SRS rates (joined with ACS population)
- `nibrs_crime_rates.csv` — NIBRS rates (joined with ACS population)

### Fact Sheet (`data/processed/`)
- `baltimore_factsheet.csv` — Wide format, now includes 25 metrics (4 crime metrics doubled)
- `baltimore_factsheet_long.csv` — Long format for Power BI
- `baltimore_factsheet_metadata.csv` — Metadata for all 25 metrics

### Visualizations (`data/visualizations/`)
- `part1_crime_rate_per_1k.png` — Dual SRS/NIBRS line plot
- `violent_crime_rate_per_1k.png` — Dual SRS/NIBRS line plot
- `property_crime_rate_per_1k.png` — Dual SRS/NIBRS line plot
- `homicide_count.png` — Dual SRS/NIBRS line plot
- 4 additional NIBRS-only plots (hidden from primary dashboard)

---

## Overlap Period Analysis (2022-2024)

Sample comparison from the factsheet:

| Year | Part 1 (SRS) | Part 1 (NIBRS) | Difference | % Difference |
|------|--------------|----------------|------------|--------------|
| 2022 | 56.87        | 55.92          | -0.95      | -1.7%        |
| 2023 | 72.77        | 73.50          | +0.73      | +1.0%        |
| 2024 | 60.44        | 62.04          | +1.60      | +2.6%        |

**Observation:** Counts are remarkably similar during overlap period. The expected ~10.6% NIBRS increase (due to hierarchy rule elimination) is **not observed** in Baltimore's data. This suggests:
1. Most Baltimore incidents are single-offense (hierarchy rule rarely applied)
2. Multi-offense incidents were already captured separately in SRS
3. The national 10.6% estimate may not apply uniformly to all jurisdictions

---

## Dashboard Display Guidance

### For Plots
- Show SRS line (blue) for historical context (2012-2024)
- Show NIBRS line (orange, dashed) for current reporting (2022-present)
- Overlap period (2022-2024) allows users to see both methodologies side-by-side
- After 2024, only NIBRS line continues

### For Metadata/Caveats
**SRS metrics:**
```
⚠️ Data quality issues from May 2021 due to BPD Records Management System
transition — 2021 and 2022 annual totals are likely understated.
⚠️ SRS reporting ended 2024; see NIBRS dataset for 2025+.
```

**NIBRS metrics:**
```
⚠️ NIBRS reporting began in 2022 with full transition Jan 1, 2025.
⚠️ NIBRS eliminates the hierarchy rule, so incident counts are theoretically
~10.6% higher than SRS for the same time period (multiple offenses per incident
now captured). However, Baltimore's overlap data shows minimal difference.
⚠️ NOT directly comparable to SRS Part 1 data (2010-2024).
```

---

## Next Steps

### Immediate
- [x] Update ACS to 2024 ✅
- [x] Add NIBRS pipeline ✅
- [x] Create dual-line visualizations ✅
- [x] Extend data through present (2026) ✅
- [ ] **Commit and push to GitHub** (pending)

### Future Enhancements
1. **2025+ NIBRS-only data** — Once 2025 completes, add full-year NIBRS data
2. **Separate NIBRS report** — Consider a dedicated NIBRS dashboard showing the expanded crime types (vandalism, fraud, etc.)
3. **Neighborhood-level NIBRS** — NIBRS dataset includes geocoding; can aggregate to CSAs when Phase 2 starts
4. **Time series analysis** — Use overlap period to calibrate trend forecasting models

---

## Files Modified

### New Files
- `src/pipelines/nibrs.py` — NIBRS API client
- `scripts/extend_to_present.py` — Extrapolate data to current year
- `NIBRS_IMPLEMENTATION.md` (this file)

### Modified Files
- `src/utils/config.py` — Updated ACS years to 2024, added NIBRS constants
- `src/pipelines/datasets.py` — Added NIBRS dataset + pull function, extrapolation support
- `src/pipelines/metrics.py` — Added 4 NIBRS metrics
- `src/run_factsheet.py` — Wired NIBRS into pipeline
- `scripts/plot_factsheet.py` — Dual-line plotting for crime metrics

---

## Testing

Pipeline tested successfully:
```
✓ 11 ACS datasets pulled (2005-2024, excluding 2020)
✓ SRS crime data (13 years: 2012-2024)
✓ NIBRS crime data (5 years: 2022-2026 partial)
✓ 25 metrics computed (21 original + 4 NIBRS)
✓ 24 visualizations generated (4 with dual lines)
✓ Validation: 0 errors, 6 warnings (expected nulls for NIBRS pre-2022)
```

---

## References
- [BPD NIBRS Transition Announcement](https://www.baltimorepolice.org/nibrs)
- [FBI NIBRS Overview](https://www.fbi.gov/how-we-can-help-you/more-fbi-services-and-information/ucr/nibrs)
- [Open Baltimore NIBRS Dataset](https://data.baltimorecity.gov/datasets/baltimore::nibrs-group-a-crime-data)
- [Congressional Research Service: NIBRS Benefits and Issues](https://www.congress.gov/crs-product/R46668)

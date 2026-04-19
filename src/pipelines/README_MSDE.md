# MSDE Report Card Data Pipeline

Automated pipeline for downloading and processing Maryland State Department of Education (MSDE) School Report Card data.

## Overview

The MSDE Report Card includes school-level accountability data and star ratings for all Maryland public schools. This pipeline automates downloading, cleaning, and standardizing this data for Baltimore City schools.

## Data Sources

- **Source**: Maryland Report Card Portal
- **URL**: https://reportcard.msde.maryland.gov/
- **Download Page**: https://reportcard.msde.maryland.gov/Graphs/#/DataDownloads/datadownload
- **Update Frequency**: Annual (released November-December for previous school year)
- **Historical Availability**: **4 years only** (2022-2025)
  - ⚠️ 2020-2021: No report cards published (COVID pandemic)
  - ⚠️ 2019 and earlier: Different accountability system; data not available in this format
  - ✅ 2022-2025: All years available (current star rating methodology)
  - 🔮 2026+: Future years will auto-discover when published

**Why only 4 years?** A comprehensive search of the MSDE download portal confirmed that only 2022-2025 data exists in the current downloadable format. Pre-2022 data used a different accountability system and is not available via the same download structure.

## Datasets

### 1. Accountability Schools (Summary Data)

**File**: `msde_accountability_schools.csv`

School-level summary with star ratings and total points earned.

**Key Columns**:
- `year` - School year (e.g., 2025 = 2024-2025 school year)
- `school` - School code (4-digit unique ID)
- `school_name` - School name
- `rating` - Star rating (1-5)
- `total_points_earned_percentage` - Points earned as % of possible

**Use Cases**:
- Compare school performance over time
- Identify top/bottom performing schools
- Track improvement/decline trends
- Visualize star rating distributions

### 2. Accountability Details (Disaggregated by Indicator & Student Group)

**File**: `msde_accountability_details.csv`

Detailed indicator-level data disaggregated by student subgroup.

**Key Columns**:
- `year` - School year
- `school` - School code
- `school_name` - School name
- `grade_span` - E=Elementary, M=Middle, H=High
- `summary_group_title` - Student group (All Students, Black/African American, Economically Disadvantaged, etc.)
- `indicator_name` - Accountability indicator (Academic Achievement, Academic Progress, Chronic Absenteeism, etc.)
- `measure_name` - Specific measure (Percent Proficient, Growth Percentile, etc.)
- `subject_title` - Subject (Mathematics, ELA, Science, or blank)
- `measure_earned_points` - Points earned for this measure
- `measure_result` - Raw value (%, count, etc.)

**Use Cases**:
- Analyze achievement gaps by student group
- Track chronic absenteeism trends
- Compare academic progress across schools
- Identify schools excelling with specific populations

## Usage

### Basic Usage (Recommended)

```python
from src.pipelines.msde_report_card import (
    ACCOUNTABILITY_DATA,
    ACCOUNTABILITY_DETAILS,
    pull_and_clean_msde_dataset,
)

# Download and process accountability schools data (star ratings)
df_schools = pull_and_clean_msde_dataset(
    ACCOUNTABILITY_DATA,
    years=[2022, 2023, 2024, 2025],  # Specify years (or None for all available)
    save=True,                        # Save to data/datasets/
    baltimore_city_only=True,         # Filter to Baltimore City only
)

# Download and process accountability details (disaggregated)
df_details = pull_and_clean_msde_dataset(
    ACCOUNTABILITY_DETAILS,
    years=[2022, 2023, 2024, 2025],
    save=True,
    baltimore_city_only=True,
)
```

### Advanced: Custom Year Range

```python
# Pull all available years (2022-present)
df_schools = pull_and_clean_msde_dataset(
    ACCOUNTABILITY_DATA,
    years=None,  # Defaults to all available years (2022-present)
    save=True,
)

# Or specify specific years
df_schools = pull_and_clean_msde_dataset(
    ACCOUNTABILITY_DATA,
    years=[2023, 2024, 2025],  # Just the last 3 years
    save=True,
)
```

### Advanced: Manual Download Only

```python
from src.pipelines.msde_report_card import download_all_years

# Download raw files without processing
file_map = download_all_years(
    years=[2025],
    file_types=["accountability_data", "accountability_details"],
    force_redownload=False,  # Skip if already downloaded
)
# Returns: {2025: {"accountability_data": Path(...), "accountability_details": Path(...)}}
```

## Output Structure

### Raw Data
- **Location**: `data/raw/msde_report_card/`
- **Files**:
  - `2025_Accountability_Schools.csv` (extracted from zip)
  - `2025_Accountability_Detail.csv` (extracted from zip)
  - `accountability_data_2025.zip` (original download)
  - `accountability_details_2025.zip` (original download)

### Processed Data
- **Location**: `data/datasets/`
- **Files**:
  - `msde_accountability_schools.csv` - Combined multi-year summary data (Baltimore City)
  - `msde_accountability_schools_data_dictionary.csv` - Column definitions
  - `msde_accountability_details.csv` - Combined multi-year detail data (Baltimore City)
  - `msde_accountability_details_data_dictionary.csv` - Column definitions

## File ID Discovery

The MSDE download portal uses numeric file IDs (not year-based URLs). The pipeline includes hard-coded mappings for all available years:

| Year | Accountability Data ID | Accountability Details ID | Status |
|------|------------------------|---------------------------|--------|
| 2022 | 476                    | 477                       | ✅ Available |
| 2023 | 496                    | 497                       | ✅ Available |
| 2024 | 536                    | 538                       | ✅ Available |
| 2025 | 572                    | 574                       | ✅ Available |
| 2026 | TBD                    | TBD                       | 🔮 Auto-discovery |

**No older data available**: A comprehensive search of file IDs 100-700 confirmed that 2022-2025 are the only years available in the current accountability format.

For future years (2026+), the pipeline will auto-discover file IDs by searching the range 500-700. This may take 1-2 minutes for new years.

## Adding New Years

When a new report card is released (typically November-December):

1. **Auto-discovery** (easiest):
   ```python
   # Pipeline will auto-discover new year's file IDs
   df = pull_and_clean_msde_dataset(ACCOUNTABILITY_DATA, years=None)
   ```

2. **Manual update** (faster):
   - Find the new file IDs manually from the download page
   - Add to `KNOWN_FILE_IDS` dict in `src/pipelines/msde_report_card.py`

## Limitations & Caveats

1. **Only 4 Years Available**: Despite the pipeline's design to pull 10 years, only 2022-2025 data exists in the current format:
   - 2020-2021: No report cards (COVID)
   - 2019 and earlier: Different accountability system (not available via this download structure)
   - This is a data availability limitation, not a pipeline limitation

2. **Methodology Changes**: The 2022 star rating system differs from pre-2022 accountability. Direct comparisons to historical data (if obtained from other sources) may not be valid.

3. **Data Quality**: Small schools or student groups may have suppressed values (marked as "<= 5.0") to protect student privacy.

4. **Baltimore City Only**: Default filter is Baltimore City (LEA=30). To get all Maryland schools, set `baltimore_city_only=False`.

5. **File ID Discovery**: Future years (2026+) require auto-discovery by searching ~200 file IDs, taking 1-2 minutes. Known years (2022-2025) are instant.

## Integration with Factsheet

To add MSDE metrics to the Baltimore factsheet:

1. Define metrics in `src/pipelines/metrics.py` (e.g., `pct_schools_3plus_stars`)
2. Add to `ALL_FACTSHEET_METRICS`
3. Update `src/run_factsheet.py` to include MSDE datasets

Example metric:
```python
from src.pipelines.msde_report_card import ACCOUNTABILITY_DATA

# Metric: Percentage of schools with 3+ stars
def compute_pct_schools_3plus_stars(df):
    total = len(df[df["rating"].notna()])
    three_plus = len(df[df["rating"].astype(float) >= 3])
    return round(100 * three_plus / total, 1) if total > 0 else None
```

## Testing

Run the test script to verify the pipeline:

```bash
python3 test_msde_pipeline.py
```

Expected output: Downloads and processes 4 years (2022-2025) for Baltimore City, producing ~590 school records and ~11,000 detail records.

## Maintenance

- **When**: Check for new data in November-December each year
- **Update**: Run pipeline with `years=None` to auto-discover new year, or manually add file ID to `KNOWN_FILE_IDS`
- **Verify**: Compare row counts year-over-year; Baltimore City typically has ~140-150 schools

## References

- [Maryland Report Card Portal](https://reportcard.msde.maryland.gov/)
- [User Guide (2024)](https://reportcard.msde.maryland.gov/HelpGuides/MSDEReportCard_UserGuide_2024_v1.pdf)
- [Accountability System Overview](https://reportcard.msde.maryland.gov/HelpGuides/ReportCard_Overview_2025_v1.pdf)
- [MSDE Press Release (2024)](https://news.maryland.gov/msde/md-report-card-2024/)

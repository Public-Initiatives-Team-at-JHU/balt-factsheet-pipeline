# JHU Public Impact Data Pipelines

Data pipelines for the JHU Public Impact Initiatives team's internal dashboard. Pulls public data about Baltimore City from Census, BLS, MSDE, and other federal/state/local sources, producing clean datasets and computed metrics for Power BI dashboards on SharePoint.

## Quick Start

```bash
# Install dependencies
pip install requests pandas

# Run the fact sheet pipeline (once built — Step 8)
python -m src.run_factsheet

# Run tests
pip install pytest
pytest
```

## Architecture

Three-layer data pipeline, designed to map to Azure's medallion architecture when ready to migrate:

```
Census API  →  data/raw/       →  data/datasets/      →  data/processed/
(Layer 1)      Raw JSON            Clean CSVs              Dashboard metrics
               Audit trail         Reusable datasets       Fact sheet numbers
                                   + data dictionaries     + methodology docs
```

**Layer 1 — Raw** (`data/raw/`): Exact API responses saved as JSON. Timestamped filenames so you never overwrite a previous pull. If a number looks wrong, trace it here.

**Layer 2 — Clean datasets** (`data/datasets/`): One CSV per Census table with human-readable column names. Each CSV has a companion `_data_dictionary.csv` explaining every column. Anyone on the team can grab these for their own analysis without understanding the pipeline code.

**Layer 3 — Computed metrics** (`data/processed/`): Dashboard-ready numbers in a flat table, plus a `methodology.csv` documenting every formula in plain English (designed to import as a Microsoft List on SharePoint).

## Project Structure

```
src/
  pipelines/
    census_acs.py       # Census ACS 1-Year API client
    census_pop.py       # Census PEP (Population Estimates Program)
    bls.py              # BLS LAUS (unemployment statistics)
    open_baltimore.py   # Open Baltimore crime data
    nibrs.py            # BPD NIBRS crime data (2022+)
    msde_report_card.py # MSDE School Report Card data
    datasets.py         # Clean dataset definitions (ACSDataset dataclass)
    metrics.py          # Dashboard metric definitions (Metric dataclass)
    README_MSDE.md      # Documentation for MSDE pipeline
  utils/
    config.py           # All constants: FIPS codes, API URLs, output schemas
    io.py               # File I/O for all three data layers
tests/
  test_datasets.py      # 27 tests — dataset layer (mocked API calls)
  test_metrics.py       # 21 tests — metric computation
  test_io.py            # 11 tests — file I/O
data/
  raw/                  # Layer 1 (gitignored)
  datasets/             # Layer 2 (gitignored)
  processed/            # Layer 3 (gitignored)
docs/
  BNIA_Indicator_Data_Sources.xlsx  # 63-indicator reference
```

## How It Works

### 1. Define a dataset (what to pull)

Each Census table is defined as an `ACSDataset` dataclass in `datasets.py`:

```python
TOTAL_POPULATION = ACSDataset(
    table_id="B01003",
    name="total_population",
    title="Total Population",
    description="Total population count from ACS 5-Year estimates.",
    columns=[
        ColumnDef(
            census_variable="B01003_001E",
            name="total_population",
            description="Total population estimate",
            universe="Total population",
        ),
        ColumnDef(
            census_variable="B01003_001M",
            name="total_population_moe",
            description="Margin of error",
            universe="Total population",
        ),
    ],
)
```

### 2. Pull and clean (raw API → clean CSV)

```python
from src.pipelines.datasets import TOTAL_POPULATION, pull_and_clean_dataset

df = pull_and_clean_dataset(TOTAL_POPULATION, years=[2020, 2021, 2022, 2023])
```

This produces:
- `data/raw/acs5_B01003_city_2023_*.json` (one per year)
- `data/datasets/acs5_total_population.csv`
- `data/datasets/acs5_total_population_data_dictionary.csv`

### 3. Define a metric (how to compute the dashboard number)

```python
TOTAL_POPULATION_METRIC = Metric(
    id="total_population",
    name="Total Population",
    description="Total population of Baltimore City",
    compute=lambda row: row["total_population"],
    source_dataset="acs5_total_population",
    source_table="B01003",
    formula_description="Direct read of B01003_001E",
    ...
)
```

### 4. Compute metrics (clean CSV → dashboard output)

```python
from src.pipelines.metrics import compute_all_metrics, build_methodology_table

dashboard = compute_all_metrics([TOTAL_POPULATION_METRIC], {"acs5_total_population": df})
methodology = build_methodology_table([TOTAL_POPULATION_METRIC])
```

## Configuration

All constants live in `src/utils/config.py`:

| Constant | Value | Purpose |
|----------|-------|---------|
| `STATE_FIPS` | `"24"` | Maryland |
| `COUNTY_FIPS` | `"510"` | Baltimore City (independent city) |
| `ACS_YEARS` | `[2020, 2021, 2022, 2023]` | Vintage years to pull |
| `CENSUS_API_KEY` | env `CENSUS_API_KEY` | Optional — higher rate limits |
| `BLS_API_KEY` | env `BLS_API_KEY` | Optional — higher rate limits |

## Data Sources

### Census Bureau
- **ACS 1-Year**: Population, demographics, income, employment, housing (2005-2024)
- **PEP**: Annual population estimates (2020-2023)
- API Key: https://api.census.gov/data/key_signup.html (optional, higher rate limits)

### Bureau of Labor Statistics (BLS)
- **LAUS**: Monthly unemployment rates (2005-present)
- API Key: https://data.bls.gov/registrationEngine/ (optional, higher rate limits)

### Maryland State Department of Education (MSDE)
- **School Report Card**: Star ratings, accountability scores, performance indicators (2022-2025)
- No API key required
- Documentation: `src/pipelines/README_MSDE.md`

### Open Baltimore
- **Crime Data**: BPD Part 1 crimes (SRS: 2012-2024, NIBRS: 2022+)
- No API key required

Set API keys as environment variables:

```bash
export CENSUS_API_KEY="your-key-here"
export BLS_API_KEY="your-key-here"
```

## Tests

```bash
pytest                    # run all 59 tests
pytest tests/test_io.py   # just I/O tests
pytest -v                 # verbose output
```

Tests mock all Census API calls — no network required, no rate limits consumed.

## Build Progress

| Step | Status | Description |
|------|--------|-------------|
| 1 | ✅ Done | Project skeleton, config, .gitignore |
| 2 | ✅ Done | ACS API client (fetch city, tracts, verify variables) |
| 3 | ✅ Done | Raw data saving (Layer 1 I/O) |
| 4 | ✅ Done | Clean dataset layer + B01003 Total Population |
| 5 | ✅ Done | Metric computation layer + Total Population metric |
| 6 | ✅ Done | All ACS 1-Year indicators (11 tables, 17 metrics) |
| 7 | ✅ Done | BLS LAUS unemployment pipeline |
| 8 | ✅ Done | Open Baltimore crime pipeline (SRS + NIBRS) |
| 9 | ✅ Done | Census PEP pipeline (annual population estimates) |
| 10 | ✅ Done | **MSDE Report Card pipeline (school performance)** |
| 11 | ✅ Done | Batch runner (`run_factsheet.py`) |
| 12 | ✅ Done | Data validation framework |
| 13 | Pending | Tract-level fetching (Phase 2 - neighborhood level) |
| 14 | Pending | CSA aggregation (Phase 2) |

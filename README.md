# JHU Public Impact Data Pipelines

Data pipelines for the JHU Public Impact Initiatives team's internal dashboard. Pulls public data about Baltimore City from Census, BLS, and other federal/local sources, producing clean datasets and computed metrics for Power BI dashboards on SharePoint.

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
    census_acs.py       # Census ACS 5-Year API client
    datasets.py         # Clean dataset definitions (ACSDataset dataclass)
    metrics.py          # Dashboard metric definitions (Metric dataclass)
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

## API Keys

Both Census and BLS APIs work without keys (lower rate limits). To register:

- **Census**: https://api.census.gov/data/key_signup.html
- **BLS**: https://data.bls.gov/registrationEngine/

Set as environment variables:

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
| 1 | Done | Project skeleton, config, .gitignore |
| 2 | Done | ACS API client (fetch city, tracts, verify variables) |
| 3 | Done | Raw data saving (Layer 1 I/O) |
| 4 | Done | Clean dataset layer + B01003 Total Population |
| 5 | Done | Metric computation layer + Total Population metric |
| 6 | Pending | Median Household Income (B19013) |
| 7 | Pending | Remaining 6 indicators (B23025, B15003, B25091, B25070, B25010) |
| 8 | Pending | Batch runner (`run_factsheet.py`) |
| 9 | Pending | Data validation |
| 10 | Pending | Variable verification utility |
| 11 | Pending | Census PEP pipeline (annual population estimates) |
| 12 | Pending | Tract-level fetching (Phase 2 foundation) |
| 13 | Pending | Logging and error handling |

"""
Central configuration for JHU Public Impact data pipelines.

All constants, API endpoints, FIPS codes, and file paths live here.
When migrating to Azure Data Lake, swap the paths — no pipeline code changes needed.
"""

import os
from pathlib import Path

# ── Project paths ────────────────────────────────────────────────────────────
# All storage paths are centralized here so swapping local → ADLS is a config change.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DATASETS_DIR = DATA_DIR / "datasets"
PROCESSED_DIR = DATA_DIR / "processed"

# ── Baltimore City FIPS codes ────────────────────────────────────────────────
STATE_FIPS = "24"          # Maryland
COUNTY_FIPS = "510"        # Baltimore City (independent city)
COUNTY_FIPS_FULL = "24510" # Combined for BLS queries

# ── Census API ───────────────────────────────────────────────────────────────
CENSUS_API_BASE = "https://api.census.gov/data"
CENSUS_ACS_BASE = f"{CENSUS_API_BASE}/{{year}}/acs/acs5"
CENSUS_PEP_BASE = f"{CENSUS_API_BASE}/{{year}}/pep/charv"
CENSUS_API_KEY = os.environ.get("CENSUS_API_KEY", "")

# ACS vintage range for fact sheet trend data
# Latest available ACS 5-year: 2023 (covers 2019-2023)
# Earliest for trend: 2020 vintage (covers 2016-2020)
ACS_LATEST_YEAR = 2023
TREND_START_YEAR = 2020
ACS_YEARS = list(range(TREND_START_YEAR, ACS_LATEST_YEAR + 1))  # [2020, 2021, 2022, 2023]

# PEP years — population estimates available 2020-2023
PEP_YEARS = list(range(2020, 2024))

# Census API limits
CENSUS_MAX_VARIABLES_PER_CALL = 50

# ── BLS API ──────────────────────────────────────────────────────────────────
BLS_API_BASE = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_LAUS_SERIES = "LAUST245100000000003"  # Baltimore City unemployment rate
BLS_API_KEY = os.environ.get("BLS_API_KEY", "")

# ── Open Baltimore (Socrata) ─────────────────────────────────────────────────
OPEN_BALT_BASE = "https://data.baltimorecity.gov/resource"

# ── BNIA CSAs ────────────────────────────────────────────────────────────────
NUM_CSAS = 55  # Baltimore has 55 Community Statistical Areas

# ── Output schema ────────────────────────────────────────────────────────────
# Dashboard output columns (one row per observation)
# indicator_id is the stable join key; indicator_name is the display label.
DASHBOARD_COLUMNS = [
    "indicator_id",
    "geography",
    "indicator_name",
    "value",
    "margin_of_error",
    "year",
    "period",
    "source",
    "source_url",
    "last_updated",
]

# Methodology table columns (designed to map to a SharePoint Microsoft List)
# indicator_id joins to DASHBOARD_COLUMNS for Power BI relationships.
METHODOLOGY_COLUMNS = [
    "indicator_id",
    "indicator_name",
    "description",
    "formula",
    "source_name",
    "source_table",
    "source_dataset",
    "source_url",
    "unit",
    "update_frequency",
    "geographic_level",
    "caveats",
    "last_verified",
]

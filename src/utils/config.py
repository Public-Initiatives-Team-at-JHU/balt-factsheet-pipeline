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
CENSUS_ACS1_BASE = f"{CENSUS_API_BASE}/{{year}}/acs/acs1"
CENSUS_ACS5_BASE = f"{CENSUS_API_BASE}/{{year}}/acs/acs5"
CENSUS_PEP_BASE = f"{CENSUS_API_BASE}/{{year}}/pep/population"
CENSUS_API_KEY = os.environ.get("CENSUS_API_KEY", "")

# ACS 1-Year estimates: city-level fact sheet (more current, single-year snapshot)
# NOTE: 2020 ACS 1-Year was NOT released due to COVID data collection issues.
# Not all tables are available from 2005 — each dataset specifies its own start_year.
ACS1_LATEST_YEAR = 2023
ACS1_EARLIEST_YEAR = 2005  # First year ACS 1-Year was released

def acs1_years(start: int = ACS1_EARLIEST_YEAR) -> list:
    """Generate ACS 1-Year vintage years from start to latest, excluding 2020."""
    return [y for y in range(start, ACS1_LATEST_YEAR + 1) if y != 2020]

# 5-Year estimates: tract/neighborhood level (larger sample, small geographies)
ACS_LATEST_YEAR = 2023
TREND_START_YEAR = 2020
ACS5_YEARS = list(range(TREND_START_YEAR, ACS_LATEST_YEAR + 1))  # [2020, 2021, 2022, 2023]

# PEP — 2020-base series, vintage 2023 is the latest available
# A single vintage call returns all years via DATE_CODE; we always call the latest.
PEP_LATEST_VINTAGE = 2023
PEP_START_YEAR = 2020  # 2020-base series starts with July 1, 2020 estimates

# Census API limits
CENSUS_MAX_VARIABLES_PER_CALL = 50

# ── BLS API ──────────────────────────────────────────────────────────────────
BLS_API_BASE = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_LAUS_SERIES = "LAUCN245100000000003"  # Baltimore City unemployment rate (county, NSA)
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

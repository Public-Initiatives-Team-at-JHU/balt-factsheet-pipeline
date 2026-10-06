"""
Central configuration for JHU Public Impact data pipelines.

All constants, API endpoints, FIPS codes, and file paths live here.
When migrating to Azure Data Lake, swap the paths — no pipeline code changes needed.

New to this code? Settings you might actually change:
- ACS year: detected automatically from the Census API (see
  latest_acs_vintage). To force a specific year, set the ACS1_VINTAGE
  environment variable, e.g. `ACS1_VINTAGE=2024 python3 -m src.run_factsheet`.
- PEP_LATEST_VINTAGE: bump this when Census publishes a new population
  estimates vintage.
- API keys: never put keys in this file. Set CENSUS_API_KEY / BLS_API_KEY
  as environment variables (see README).
"""

import functools
import logging
import os
from datetime import date
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# ── Project paths ────────────────────────────────────────────────────────────
# All storage paths are centralized here so swapping local → ADLS is a config change.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "00 raw"
DATASETS_DIR = DATA_DIR / "01 clean"


def processed_dir_from_env() -> Path:
    """Folder where fact sheet outputs are written.

    Defaults to data/02 processed/. Set the FACTSHEET_OUTPUT_DIR environment
    variable to a OneDrive-synced SharePoint folder to publish outputs there
    directly instead of uploading them by hand.
    """
    override = os.environ.get("FACTSHEET_OUTPUT_DIR")
    if override:
        return Path(override).expanduser()
    return DATA_DIR / "02 processed"


PROCESSED_DIR = processed_dir_from_env()

# Stamped on every metadata output so published files trace back to the code.
PIPELINE_REPO_URL = "https://github.com/Public-Initiatives-Team-at-JHU/balt-factsheet-pipeline"

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
ACS1_EARLIEST_YEAR = 2005  # First year ACS 1-Year was released
TREND_START_YEAR = 2020

# Latest vintage is probed at runtime (see latest_acs_vintage) rather than
# hardcoded, so a new release is picked up without a code change. These are the
# newest vintages confirmed published — used when the probe can't reach Census.
#
# As of 2026-09-22 the 2025 ACS 1-Year is NOT released: Census has it on hold
# pending the Commerce "Disclosure Avoidance for Statistical Products"
# administrative order, with no announced date. Until it lands, the probe
# resolves to these values.
ACS1_FALLBACK_YEAR = 2024
ACS5_FALLBACK_YEAR = 2024

_ACS_FALLBACK_VINTAGE = {
    "acs1": ACS1_FALLBACK_YEAR,
    "acs5": ACS5_FALLBACK_YEAR,
}
_VINTAGE_PROBE_TIMEOUT = 10  # seconds


@functools.lru_cache(maxsize=None)
def latest_acs_vintage(dataset: str = "acs1") -> int:
    """Resolve the newest published ACS vintage for `dataset` ("acs1"/"acs5").

    Walks back from the current calendar year, asking the Census API which
    vintages exist, and returns the first one that does. Never guesses past
    what Census has actually published, and never returns less than the
    confirmed fallback.

    Set the ``ACS1_VINTAGE`` / ``ACS5_VINTAGE`` environment variable to pin a
    vintage explicitly — needed to reproduce an earlier run once a new release
    shifts the default.

    Cached for the life of the process; call ``cache_clear()`` to re-probe.
    """
    if dataset not in _ACS_FALLBACK_VINTAGE:
        raise ValueError(
            f"Unknown ACS dataset {dataset!r}; "
            f"expected one of {sorted(_ACS_FALLBACK_VINTAGE)}"
        )

    fallback = _ACS_FALLBACK_VINTAGE[dataset]

    pinned = os.environ.get(f"{dataset.upper()}_VINTAGE", "").strip()
    if pinned:
        try:
            year = int(pinned)
        except ValueError:
            logger.warning(
                "Ignoring invalid %s_VINTAGE=%r; probing Census instead",
                dataset.upper(), pinned,
            )
        else:
            logger.info("%s vintage pinned to %d via environment", dataset, year)
            return year

    # fallback is known-good, so there's no reason to probe it or below.
    for year in range(date.today().year, fallback, -1):
        url = f"{CENSUS_API_BASE}/{year}/acs/{dataset}.json"
        try:
            resp = requests.get(url, timeout=_VINTAGE_PROBE_TIMEOUT)
        except requests.RequestException as exc:
            logger.warning(
                "%s vintage probe failed (%s); falling back to %d",
                dataset, exc, fallback,
            )
            return fallback

        if resp.status_code == 200:
            logger.info("%s vintage resolved to %d", dataset, year)
            return year

    logger.info("%s vintage resolved to %d (fallback)", dataset, fallback)
    return fallback


def acs1_years(start: int = ACS1_EARLIEST_YEAR) -> list:
    """Generate ACS 1-Year vintage years from start to latest, excluding 2020."""
    return [y for y in range(start, latest_acs_vintage("acs1") + 1) if y != 2020]


# 5-Year estimates: tract/neighborhood level (larger sample, small geographies)
def acs5_years(start: int = TREND_START_YEAR) -> list:
    """Generate ACS 5-Year vintage years from start to latest."""
    return list(range(start, latest_acs_vintage("acs5") + 1))


# data.census.gov table links are vintage-specific. Metric definitions are
# module-level, so they carry this token and resolve it when rows are emitted —
# baking the vintage in at import time would fire a network probe on import.
ACS1_VINTAGE_TOKEN = "{acs1_vintage}"
ACS1_TABLE_URL = f"https://data.census.gov/table/ACSDT1Y{ACS1_VINTAGE_TOKEN}"


def resolve_acs_vintage_tokens(url: str) -> str:
    """Substitute the ACS vintage token in a source URL, if present."""
    if ACS1_VINTAGE_TOKEN not in url:
        return url
    return url.replace(ACS1_VINTAGE_TOKEN, str(latest_acs_vintage("acs1")))

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

# ── Open Baltimore ───────────────────────────────────────────────────────────
OPEN_BALT_BASE = "https://data.baltimorecity.gov/resource"

# SRS crime data (legacy, through 2024)
SRS_START_YEAR = 2012  # 2010-2011 incomplete in source
SRS_END_YEAR = 2024    # SRS reporting ended Dec 31, 2024

# NIBRS crime data (current, 2022-present)
NIBRS_START_YEAR = 2022  # NIBRS dataset starts Jan 1, 2022
# Overlap period 2022-2024 allows SRS/NIBRS comparison

# ── BNIA CSAs ────────────────────────────────────────────────────────────────
NUM_CSAS = 55  # Baltimore has 55 Community Statistical Areas

# ── Output schema ────────────────────────────────────────────────────────────
# Dashboard output columns (one row per observation)
# indicator_id is the stable join key; indicator_name is the display label.
DASHBOARD_COLUMNS = [
    "indicator_id",
    "geography",
    "indicator_name",
    "demographic_group",
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

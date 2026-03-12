from __future__ import annotations

"""
Open Baltimore (Socrata) API client.

Baltimore City publishes public data via the Socrata SODA API at
data.baltimorecity.gov. This module provides a generic SODA client and
dataset-specific fetch/aggregate functions.

⚠️  DATA QUALITY CAVEAT — BPD Crime Data:
The Part 1 Victim Based Crime dataset (wsfq-mvij) has known data quality
issues beginning in May 2021 due to BPD's transition to a new Records
Management System. 2021 and 2022 annual totals are likely understated.
Current incident data (2022-present) is in the separate NIBRS Group A
dataset which uses a different crime classification. Until BPD resolves
the transition gap, crime trend data should be presented with this caveat.

Socrata SODA API docs: https://dev.socrata.com/docs/endpoints.html
Open Baltimore portal:  https://data.baltimorecity.gov
"""

import requests

from src.utils.config import OPEN_BALT_BASE

# ── Dataset IDs ───────────────────────────────────────────────────────────────

BPD_PART1_CRIME_DATASET_ID = "wsfq-mvij"   # BPD Part 1 Victim Based Crime Data
DEMO_PERMITS_DATASET_ID    = "ad7n-rq74"   # Housing Permits - Demolition

# ── Crime type classification ─────────────────────────────────────────────────
# Maps BPD Description values to FBI UCR Part 1 violent/property categories.
# Verified against BPD dataset documentation. Needs re-check if BPD description
# values change in future data updates.

VIOLENT_CRIME_TYPES = {
    "HOMICIDE",
    "RAPE",
    "ROBBERY - CARJACKING",
    "ROBBERY - COMMERCIAL",
    "ROBBERY - RESIDENCE",
    "ROBBERY - STREET",
    "AGG. ASSAULT",
    "SHOOTING",          # BPD-specific; treated as violent for this dataset
}

PROPERTY_CRIME_TYPES = {
    "BURGLARY",
    "LARCENY",
    "LARCENY FROM AUTO",
    "AUTO THEFT",
    "ARSON",
}

# Convenience set for all Part 1 types
PART1_CRIME_TYPES = VIOLENT_CRIME_TYPES | PROPERTY_CRIME_TYPES

# The year BPD's RMS transition introduced data quality issues
BPD_DATA_QUALITY_ISSUE_YEAR = 2021


# ── Generic SODA client ───────────────────────────────────────────────────────

def fetch_socrata(
    dataset_id: str,
    select: str | None = None,
    where: str | None = None,
    group: str | None = None,
    order: str | None = None,
    limit: int = 50000,
) -> list[dict]:
    """Make a Socrata SODA API query and return results as a list of dicts.

    Supports SQL-style SELECT/WHERE/GROUP BY/ORDER BY via Socrata SoQL.
    For aggregation queries (GROUP BY), limit of 50000 is almost always
    sufficient. For full incident-level pulls, increase limit as needed.

    Args:
        dataset_id: 4x4 Socrata dataset ID, e.g. "wsfq-mvij"
        select: SoQL SELECT clause, e.g. "description, count(*) as count"
        where: SoQL WHERE clause, e.g. "crimedatetime >= '2005-01-01'"
        group: SoQL GROUP BY clause, e.g. "description"
        order: SoQL ORDER BY clause, e.g. "crime_year ASC"
        limit: Maximum rows to return (Socrata default is 1000; always set this)

    Returns:
        List of dicts, one per row. All values are strings.

    Raises:
        requests.HTTPError: If the Socrata API returns an error.
    """
    url = f"{OPEN_BALT_BASE}/{dataset_id}.json"
    params: dict = {"$limit": limit}

    if select:
        params["$select"] = select
    if where:
        params["$where"] = where
    if group:
        params["$group"] = group
    if order:
        params["$order"] = order

    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ── Crime-specific fetch ──────────────────────────────────────────────────────

def fetch_crime_counts_by_year(
    start_year: int = 2005,
    end_year: int = 2023,
) -> list[dict]:
    """Fetch BPD Part 1 crime counts aggregated by year and description.

    Uses Socrata SoQL aggregation so we pull ~300 rows (20 years × 15 types)
    rather than 300K+ incident records. All classification/rate computation
    happens downstream in pandas.

    Args:
        start_year: First year to include (inclusive).
        end_year: Last year to include (inclusive).

    Returns:
        List of dicts with keys: crime_year, description, count.
        crime_year is an ISO datetime string ("2020-01-01T00:00:00.000").
    """
    return fetch_socrata(
        dataset_id=BPD_PART1_CRIME_DATASET_ID,
        select=(
            "date_trunc_y(CrimeDateTime) as crime_year, "
            "Description as description, "
            "count(*) as count"
        ),
        where=(
            f"CrimeDateTime >= '{start_year}-01-01T00:00:00.000' "
            f"AND CrimeDateTime < '{end_year + 1}-01-01T00:00:00.000'"
        ),
        group="date_trunc_y(CrimeDateTime), Description",
        order="crime_year ASC",
    )


def classify_crime(description: str) -> str | None:
    """Classify a BPD crime description as 'violent', 'property', or None.

    Args:
        description: BPD Description field value (case-insensitive).

    Returns:
        'violent', 'property', or None if not a Part 1 crime.
    """
    desc = description.strip().upper()
    if desc in VIOLENT_CRIME_TYPES:
        return "violent"
    if desc in PROPERTY_CRIME_TYPES:
        return "property"
    return None

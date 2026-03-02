from __future__ import annotations

"""
Census American Community Survey (ACS) API client.

City-level data uses ACS 1-Year estimates (more current, single-year snapshot).
Tract-level data uses ACS 5-Year estimates (larger sample for small geographies).

Returns raw list-of-lists as the Census API provides them — cleaning
and type conversion happen in the datasets layer.

Census API docs: https://www.census.gov/data/developers/data-sets/acs-1year.html
Variable lookup: https://api.census.gov/data/{year}/acs/acs1/groups.html
"""

import requests

from src.utils.config import (
    CENSUS_ACS1_BASE,
    CENSUS_ACS5_BASE,
    CENSUS_API_KEY,
    CENSUS_MAX_VARIABLES_PER_CALL,
    COUNTY_FIPS,
    STATE_FIPS,
)


def fetch_acs_city(variables: list[str], year: int) -> list[list[str]]:
    """Fetch ACS 1-Year data for Baltimore City (county level).

    Uses 1-Year estimates which provide a single-year snapshot. More current
    than 5-Year estimates, and Baltimore City (pop ~577K) is large enough
    to meet the 65,000 population threshold.

    Note: 2020 ACS 1-Year was not released due to COVID.

    Args:
        variables: Census variable codes, e.g. ["B01003_001E", "B01003_001M"]
        year: ACS vintage year (e.g. 2023)

    Returns:
        List of lists: [[header_row], [data_row]].
        All values are strings — type conversion happens downstream.

    Raises:
        ValueError: If more than 50 variables requested (Census API limit)
        requests.HTTPError: If the Census API returns an error
    """
    if len(variables) > CENSUS_MAX_VARIABLES_PER_CALL:
        raise ValueError(
            f"Census API allows max {CENSUS_MAX_VARIABLES_PER_CALL} variables per call, "
            f"got {len(variables)}. Split into multiple calls."
        )

    url = CENSUS_ACS1_BASE.format(year=year)
    params = {
        "get": ",".join(variables),
        "for": f"county:{COUNTY_FIPS}",
        "in": f"state:{STATE_FIPS}",
    }
    if CENSUS_API_KEY:
        params["key"] = CENSUS_API_KEY

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_acs_tracts(variables: list[str], year: int) -> list[list[str]]:
    """Fetch ACS 5-Year data for all Baltimore City census tracts.

    Same as fetch_acs_city but returns ~199 rows (one per tract).

    Args:
        variables: Census variable codes
        year: ACS vintage year

    Returns:
        List of lists: [[header_row], [tract_row_1], [tract_row_2], ...]
    """
    if len(variables) > CENSUS_MAX_VARIABLES_PER_CALL:
        raise ValueError(
            f"Census API allows max {CENSUS_MAX_VARIABLES_PER_CALL} variables per call, "
            f"got {len(variables)}. Split into multiple calls."
        )

    url = CENSUS_ACS5_BASE.format(year=year)
    params = {
        "get": ",".join(variables),
        "for": "tract:*",
        "in": f"state:{STATE_FIPS} county:{COUNTY_FIPS}",
    }
    if CENSUS_API_KEY:
        params["key"] = CENSUS_API_KEY

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def verify_variables(table_id: str, variables: list[str], year: int) -> dict:
    """Verify variable codes against the Census API groups endpoint.

    Variable codes can shift between ACS vintages. Always verify before
    building a pipeline for a new table or year.

    Args:
        table_id: ACS table ID, e.g. "B01003"
        variables: Variable codes to verify, e.g. ["B01003_001E"]
        year: ACS vintage year to check against

    Returns:
        Dict with keys:
            "valid": list of variable codes that exist
            "invalid": list of variable codes that don't exist
            "labels": dict mapping valid codes to their labels
    """
    url = f"{CENSUS_ACS5_BASE.format(year=year)}/groups/{table_id}.json"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    group_data = resp.json()
    available = group_data.get("variables", {})

    valid = []
    invalid = []
    labels = {}

    for var in variables:
        if var in available:
            valid.append(var)
            labels[var] = available[var].get("label", "")
        else:
            invalid.append(var)

    return {"valid": valid, "invalid": invalid, "labels": labels}

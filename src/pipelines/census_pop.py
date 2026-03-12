from __future__ import annotations

"""
Census Population Estimates Program (PEP) API client.

PEP provides official annual population estimates for Baltimore City.
These are model-based estimates (not survey estimates) produced by combining
the Census count with birth, death, and migration data — making them more
accurate than ACS survey estimates for year-to-year tracking.

The 2020-base series (vintage 2020 onward) covers July 1 estimates for
2020 through the latest vintage year. A single vintage call returns all
years via the DATE_CODE variable, so we always call the latest vintage.

DATE_CODE values in the 2020-base PEP:
  DATE_CODE=0: April 1, 2020 (Census day base — excluded from output)
  DATE_CODE=1: July 1, 2020
  DATE_CODE=2: July 1, 2021
  ...
  DATE_CODE=N: July 1, 2019+N

We parse year from DATE_DESC ("7/1/2020" → 2020) rather than the code offset
so the logic stays correct as new vintage years are added.

Census PEP docs:   https://www.census.gov/data/developers/data-sets/popest-popproj/popest.html
PEP variables:     https://api.census.gov/data/{year}/pep/population/variables.html
"""

import requests

from src.utils.config import (
    CENSUS_API_KEY,
    CENSUS_PEP_BASE,
    COUNTY_FIPS,
    STATE_FIPS,
)


def fetch_pep_population(vintage_year: int) -> list[list[str]]:
    """Fetch PEP population estimates for Baltimore City.

    Returns one row per time period (DATE_CODE), including both the
    April 2020 Census base and all subsequent July 1 annual estimates.
    The caller is responsible for filtering to the desired time periods.

    Args:
        vintage_year: PEP vintage year (e.g. 2023). Each vintage adds one
                      more year of estimates to the series.

    Returns:
        List of lists: [[header_row], [row_1], [row_2], ...].
        Columns: POPESTIMATE, DATE_CODE, DATE_DESC, NAME, state, county.
        All values are strings — type conversion happens downstream.

    Raises:
        requests.HTTPError: If the Census API returns an error.
    """
    url = CENSUS_PEP_BASE.format(year=vintage_year)
    params = {
        "get": "POPESTIMATE,DATE_CODE,DATE_DESC,NAME",
        "for": f"county:{COUNTY_FIPS}",
        "in": f"state:{STATE_FIPS}",
    }
    if CENSUS_API_KEY:
        params["key"] = CENSUS_API_KEY

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def parse_pep_year(date_desc: str) -> int | None:
    """Parse the calendar year from a PEP DATE_DESC string.

    PEP DATE_DESC format: "7/1/2023" or "4/1/2020 (estimates base)"
    We extract the 4-digit year from the last path segment.

    Args:
        date_desc: DATE_DESC string from PEP API response.

    Returns:
        4-digit calendar year as int, or None if parsing fails.
    """
    try:
        # Format is "M/D/YYYY" or "M/D/YYYY (estimates base)"
        # Year is the third token when split by "/"
        year_part = date_desc.strip().split("/")[2]
        # Strip anything after the year (e.g. " (estimates base)")
        return int(year_part.split()[0])
    except (IndexError, ValueError):
        return None

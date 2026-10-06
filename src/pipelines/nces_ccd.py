"""
NCES Common Core of Data (CCD) enrollment pipeline.

Fetches total K-12 district enrollment from the Urban Institute Education Data API,
which wraps NCES CCD data. No API key required.

API: https://educationdata.urban.org/api/v1/school-districts/ccd/directory/{year}/
Docs: https://educationdata.urban.org/api/v1/school-districts/ccd/directory/

Year convention: NCES uses school-year start year (2022 = SY 2022-23).
Callers convert to ending year (+1) for storage.
"""

from __future__ import annotations

import requests

EDDATA_BASE = "https://educationdata.urban.org/api/v1/"


def fetch_ccd_district_enrollment(
    leaid: str,
    start_year: int,
    end_year: int,
) -> list[dict]:
    """Fetch total K-12 enrollment for one district from NCES CCD.

    Uses the Urban Institute Education Data API directory endpoint.
    Year convention: NCES uses school-year start year (2022 = SY 2022-23).

    Args:
        leaid: NCES Local Education Agency ID (e.g. "2400090")
        start_year: First school-year start year to fetch
        end_year: Last school-year start year to fetch

    Returns:
        List of dicts with keys: year, leaid, enrollment.
        Years with no data are omitted.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status.
    """
    results = []
    for year in range(start_year, end_year + 1):
        url = f"{EDDATA_BASE}school-districts/ccd/directory/{year}/"
        resp = requests.get(url, params={"leaid": leaid}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for record in data.get("results", []):
            results.append({
                "year": record["year"],
                "leaid": record["leaid"],
                "enrollment": record["enrollment"],
            })
    return results

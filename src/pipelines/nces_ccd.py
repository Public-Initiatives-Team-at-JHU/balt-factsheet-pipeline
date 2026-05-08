from __future__ import annotations

import requests

EDDATA_BASE_URL = "https://educationdata.urban.org/api/v1/"


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
    """
    results = []
    for year in range(start_year, end_year + 1):
        url = f"{EDDATA_BASE_URL}school-districts/ccd/directory/{year}/"
        resp = requests.get(url, params={"leaid": leaid})
        resp.raise_for_status()
        data = resp.json()
        for record in data.get("results", []):
            results.append({
                "year": record["year"],
                "leaid": record["leaid"],
                "enrollment": record["enrollment"],
            })
    return results

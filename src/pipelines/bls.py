from __future__ import annotations

"""
Bureau of Labor Statistics (BLS) API client.

Fetches Local Area Unemployment Statistics (LAUS) for Baltimore City.
Monthly data from BLS is the authoritative source for unemployment rates.

BLS API docs: https://www.bls.gov/developers/
Series ID reference: https://www.bls.gov/help/hlpforma.htm#LA
LAUS overview: https://www.bls.gov/lau/
"""

import requests

from src.utils.config import BLS_API_BASE, BLS_API_KEY


def fetch_bls_laus(series_id: str, start_year: int, end_year: int) -> dict:
    """Fetch BLS LAUS time series data via API v2.

    Handles BLS API rate limits:
    - Unregistered: 10 years max per request → automatically splits into multiple calls
    - Registered: 20 years max per request → single call for most use cases

    Args:
        series_id: BLS series ID (e.g., "LAUCN245100000000003")
        start_year: First year to fetch
        end_year: Last year to fetch

    Returns:
        Raw API response dict with merged data from all calls

    Raises:
        requests.HTTPError: If the BLS API returns an error
        ValueError: If response structure is invalid
    """
    span = end_year - start_year + 1

    # If registered or within free tier limit, single call
    if BLS_API_KEY or span <= 10:
        return _bls_api_call(series_id, start_year, end_year)

    # Unregistered and > 10 years: split into multiple calls
    all_data = []
    current_start = start_year
    while current_start <= end_year:
        current_end = min(current_start + 9, end_year)  # 10 years per call
        data = _bls_api_call(series_id, current_start, current_end)
        all_data.extend(data["Results"]["series"][0]["data"])
        current_start = current_end + 1

    # Return merged response in same format as single call
    return {
        "status": "REQUEST_SUCCEEDED",
        "Results": {
            "series": [{
                "seriesID": series_id,
                "data": all_data,
            }]
        },
    }


def _bls_api_call(series_id: str, start_year: int, end_year: int) -> dict:
    """Make a single BLS API call."""
    payload = {
        "seriesid": [series_id],
        "startyear": str(start_year),
        "endyear": str(end_year),
    }

    if BLS_API_KEY:
        payload["registrationkey"] = BLS_API_KEY

    resp = requests.post(BLS_API_BASE, json=payload, timeout=30)
    resp.raise_for_status()

    data = resp.json()

    # Validate response status
    if data.get("status") != "REQUEST_SUCCEEDED":
        error_msg = data.get("message", ["Unknown error"])
        raise ValueError(f"BLS API error: {error_msg}")

    # Validate structure
    if "Results" not in data or "series" not in data["Results"]:
        raise ValueError("Invalid BLS API response structure")

    if len(data["Results"]["series"]) == 0:
        raise ValueError(f"No data returned for series {series_id}")

    return data

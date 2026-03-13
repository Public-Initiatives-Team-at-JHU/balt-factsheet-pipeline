from __future__ import annotations

"""
Open Baltimore crime data client — ArcGIS FeatureServer.

Baltimore City migrated from Socrata to ArcGIS Hub. The Part 1 (SRS)
crime dataset is now served from an ArcGIS FeatureServer:

  https://services1.arcgis.com/UWYHeuuJISiGmgXx/arcgis/rest/services/
      Part1_Crime_Beta/FeatureServer/0

Coverage: historical SRS data through 12/31/2024. As of 2025 BPD
switched to NIBRS reporting; a separate dataset covers 2025-present.

⚠️  DATA QUALITY CAVEAT:
BPD transitioned Records Management Systems in May 2021. Annual totals
for 2021 and 2022 are likely understated due to incomplete records
during the transition period.

ArcGIS REST API docs: https://developers.arcgis.com/rest/services-reference/
Open Baltimore Hub:   https://data.baltimorecity.gov
"""

import requests

# ── Endpoints ─────────────────────────────────────────────────────────────────

# Legacy SRS Part 1 crime data — confirmed via Open Baltimore Hub API 2026-03-12
BPD_PART1_FEATURESERVER = (
    "https://services1.arcgis.com/UWYHeuuJISiGmgXx/arcgis/rest/services"
    "/Part1_Crime_Beta/FeatureServer/0"
)

# Still used for legacy reference in dataset metadata
BPD_PART1_CRIME_DATASET_ID = "wsfq-mvij"

# ── Crime type classification ─────────────────────────────────────────────────
# Maps BPD Description values to FBI UCR Part 1 violent/property categories.

VIOLENT_CRIME_TYPES = {
    "HOMICIDE",
    "RAPE",
    "ROBBERY",          # Generic robbery (no subtype)
    "ROBBERY - CARJACKING",
    "ROBBERY - COMMERCIAL",
    "ROBBERY - RESIDENCE",
    "ROBBERY - STREET",
    "AGG. ASSAULT",
    # NOTE: "COMMON ASSAULT" is Part 2 (not Part 1) per FBI UCR - excluded
    "SHOOTING",         # Firearm-involved aggravated assault
}

PROPERTY_CRIME_TYPES = {
    "BURGLARY",
    "LARCENY",
    "LARCENY FROM AUTO",
    "AUTO THEFT",
    "ARSON",
}

PART1_CRIME_TYPES = VIOLENT_CRIME_TYPES | PROPERTY_CRIME_TYPES

BPD_DATA_QUALITY_ISSUE_YEAR = 2021


# ── ArcGIS REST client ────────────────────────────────────────────────────────

def fetch_arcgis_query(
    feature_server_url: str,
    where: str = "1=1",
    out_fields: str = "*",
    out_statistics: list | None = None,
    group_by: str | None = None,
    result_record_count: int = 2000,
) -> list[dict]:
    """Query an ArcGIS FeatureServer layer and return attributes as a list of dicts.

    Args:
        feature_server_url: Full URL to the FeatureServer layer (ending in /0, /1 etc.)
        where: SQL WHERE clause, e.g. "CrimeDateTime >= timestamp '2010-01-01 00:00:00'"
        out_fields: Comma-separated field names or "*" for all
        out_statistics: List of statistic dicts for aggregation queries, e.g.
            [{"statisticType": "count", "onStatisticField": "ObjectId",
              "outStatisticFieldName": "incident_count"}]
        group_by: Comma-separated field names for GROUP BY (requires out_statistics)
        result_record_count: Max records to return per request

    Returns:
        List of attribute dicts, one per result row.

    Raises:
        requests.HTTPError: On HTTP error.
        ValueError: If ArcGIS returns an error payload.
    """
    import json

    params: dict = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "false",
        "resultRecordCount": result_record_count,
        "f": "json",
    }

    if out_statistics is not None:
        params["outStatistics"] = json.dumps(out_statistics)
    if group_by is not None:
        params["groupByFieldsForStatistics"] = group_by

    resp = requests.get(f"{feature_server_url}/query", params=params, timeout=60)
    resp.raise_for_status()

    data = resp.json()

    if "error" in data:
        raise ValueError(f"ArcGIS API error: {data['error']}")

    return [f["attributes"] for f in data.get("features", [])]


# ── Crime-specific fetch ──────────────────────────────────────────────────────

def fetch_crime_counts_by_year(
    start_year: int = 2010,
    end_year: int = 2024,
) -> list[dict]:
    """Fetch BPD Part 1 crime counts aggregated by year and description.

    Makes one ArcGIS query per year (using WHERE date range + outStatistics
    GROUP BY Description). Returns a flat list of dicts with keys:
    year, description, incident_count.

    Args:
        start_year: First year to include (inclusive).
        end_year: Last year to include (inclusive).

    Returns:
        List of dicts: [{"year": 2010, "description": "HOMICIDE", "count": 24}, ...]
    """
    results = []

    for year in range(start_year, end_year + 1):
        rows = fetch_arcgis_query(
            feature_server_url=BPD_PART1_FEATURESERVER,
            where=(
                f"CrimeDateTime >= timestamp '{year}-01-01 00:00:00' "
                f"AND CrimeDateTime < timestamp '{year + 1}-01-01 00:00:00'"
            ),
            out_statistics=[{
                "statisticType": "count",
                "onStatisticField": "CrimeDateTime",
                "outStatisticFieldName": "incident_count",
            }],
            group_by="Description",
            result_record_count=200,  # ~15 crime types per year
        )
        for row in rows:
            results.append({
                "year": year,
                "description": (row.get("Description") or "").strip().upper(),
                "count": int(row.get("incident_count") or 0),
            })

    return results


def classify_crime(description: str) -> str | None:
    """Classify a BPD crime description as 'violent', 'property', or None."""
    desc = description.strip().upper()
    if desc in VIOLENT_CRIME_TYPES:
        return "violent"
    if desc in PROPERTY_CRIME_TYPES:
        return "property"
    return None

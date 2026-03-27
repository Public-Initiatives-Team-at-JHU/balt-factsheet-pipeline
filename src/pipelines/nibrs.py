from __future__ import annotations

"""
Open Baltimore NIBRS crime data client — ArcGIS FeatureServer.

Baltimore Police Department transitioned to NIBRS (National Incident-Based
Reporting System) effective January 1, 2025. This dataset covers 2022-present
and provides overlap with the legacy SRS dataset (2010-2024).

NIBRS Group A dataset on Open Baltimore:
  https://data.baltimorecity.gov/datasets/baltimore::nibrs-group-a-crime-data

NIBRS eliminates the hierarchy rule, so incident counts will be higher than
SRS for the same time period (~10.6% more offenses due to multi-offense incidents).

ArcGIS REST API docs: https://developers.arcgis.com/rest/services-reference/
"""

import requests

# ── Endpoints ─────────────────────────────────────────────────────────────────

NIBRS_GROUPA_FEATURESERVER = (
    "https://services1.arcgis.com/UWYHeuuJISiGmgXx/arcgis/rest/services"
    "/NIBRS_GroupA_Crime_Data/FeatureServer/0"
)

# ── Crime type classification ─────────────────────────────────────────────────
# Maps NIBRS Description values to FBI UCR Part 1 equivalent categories.
# NIBRS has more granular crime types than SRS, but they can be grouped
# into violent/property to maintain comparability.

VIOLENT_CRIME_TYPES_NIBRS = {
    "HOMICIDE",
    "RAPE",
    "ROBBERY",               # Generic robbery
    "ROBBERY - CARJACKING",
    "ROBBERY - COMMERCIAL",
    "AGG. ASSAULT",
    # NOTE: COMMON ASSAULT is Part 2 (not Part 1 equivalent) - excluded from violent crime rate
}

PROPERTY_CRIME_TYPES_NIBRS = {
    "BURGLARY",
    "LARCENY",
    "LARCENY FROM AUTO",
    "LARCENY OF MOTOR VEHICLE PARTS OR ACCESSORIES",  # New in NIBRS, part of larceny family
    "SHOPLIFTING",           # NIBRS separates shoplifting from generic larceny
    "AUTO THEFT",
    "ARSON",
}

PART1_EQUIVALENT_NIBRS = VIOLENT_CRIME_TYPES_NIBRS | PROPERTY_CRIME_TYPES_NIBRS

# NIBRS additions not in SRS Part 1 (excluded from Part 1 rate):
# ANIMAL CRUELTY, VANDALISM, FRAUD, INTIMIDATION, KIDNAPPING,
# EXTORTION, HUMAN TRAFFICKING, SEX OFFENSES, DRUG/NARCOTIC VIOLATIONS,
# WEAPON VIOLATIONS, PROSTITUTION, PORNOGRAPHY, STOLEN PROPERTY


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
        where: SQL WHERE clause, e.g. "CrimeDateTime >= timestamp '2022-01-01 00:00:00'"
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

def fetch_nibrs_counts_by_year(
    start_year: int = 2022,
    end_year: int = 2026,
) -> list[dict]:
    """Fetch NIBRS Group A crime counts aggregated by year and description.

    Makes one ArcGIS query per year (using WHERE date range + outStatistics
    GROUP BY Description). Returns a flat list of dicts with keys:
    year, description, incident_count.

    Args:
        start_year: First year to include (inclusive). Default 2022 (NIBRS start).
        end_year: Last year to include (inclusive).

    Returns:
        List of dicts: [{"year": 2022, "description": "HOMICIDE", "count": 24}, ...]
    """
    results = []

    for year in range(start_year, end_year + 1):
        rows = fetch_arcgis_query(
            feature_server_url=NIBRS_GROUPA_FEATURESERVER,
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
            result_record_count=200,  # ~30 NIBRS crime types per year
        )
        for row in rows:
            results.append({
                "year": year,
                "description": (row.get("Description") or "").strip().upper(),
                "count": int(row.get("incident_count") or 0),
            })

    return results


def classify_crime_nibrs(description: str) -> str | None:
    """Classify a NIBRS crime description as 'violent', 'property', or None.

    Returns None for NIBRS Group A offenses that are not Part 1 equivalents
    (e.g., COMMON ASSAULT, VANDALISM, FRAUD).
    """
    desc = description.strip().upper()
    if desc in VIOLENT_CRIME_TYPES_NIBRS:
        return "violent"
    if desc in PROPERTY_CRIME_TYPES_NIBRS:
        return "property"
    return None

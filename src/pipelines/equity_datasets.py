from __future__ import annotations

"""
Race/ethnicity equity breakdowns for the Baltimore fact sheet.

Uses Census ACS 1-Year race-iteration tables (suffix B, D, H, I) to compute
poverty rate, median household income, and homeownership rate for Baltimore's
four largest demographic groups.

Census race-iteration naming convention:
  B = Black or African American alone
  D = Asian alone
  H = White alone, not Hispanic or Latino
  I = Hispanic or Latino (of any race)

Only these four groups are included because Baltimore's other groups (AIAN, NHPI,
other race, two or more races) are too small for reliable ACS 1-Year estimates.

## Data suppression

The Census Bureau suppresses ACS 1-Year estimates when sub-group sample sizes are
too small to produce statistically reliable figures. For Baltimore City:

  - Asian poverty rate (B17001D): SUPPRESSED in ACS 1-Year for all years.
    Baltimore's Asian population (~13,000 people, ~2% of city) is too small
    for reliable single-year poverty estimates. The B17001 table's age/sex
    sub-categories further reduce per-cell sample sizes, triggering suppression.
    The Census API returns null for both B17001D_001E and B17001D_002E.
    ACS 5-Year estimates DO have this data (~21% poverty rate as of 2023).

  - Other indicators (median income, homeownership) are available for Asian
    because those tables are simpler (fewer sub-categories → larger cell counts).

Blank values in the equity output for Asian poverty rate reflect Census suppression,
not a pipeline error. See build_equity_methodology_table() for per-indicator caveats.

Output schema: year | geography | indicator_id | indicator_name |
               demographic_group | value | source | source_url | last_updated
"""

from datetime import datetime, timezone

import pandas as pd

from src.pipelines.census_acs import fetch_acs_city
from src.pipelines.datasets import ACSDataset, ColumnDef, _to_numeric
from src.utils.config import (
    ACS1_EARLIEST_YEAR,
    ACS1_TABLE_URL,
    acs1_years,
    resolve_acs_vintage_tokens,
)
from src.utils.io import save_dataset, save_raw_response, save_processed

# ── Race groups ──────────────────────────────────────────────────────────────
# Maps internal key → (Census table suffix, display label)

RACE_GROUPS: dict[str, tuple[str, str]] = {
    "black":    ("B", "Black or African American"),
    "asian":    ("D", "Asian"),
    "white_nh": ("H", "White (Non-Hispanic)"),
    "hispanic": ("I", "Hispanic or Latino"),
}

EQUITY_OUTPUT_COLUMNS = [
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

_ACS1Y_URL = ACS1_TABLE_URL  # carries {acs1_vintage}; resolved at emit time
_ACS_SOURCE = "ACS 1-Year Estimates"


# ── Dataset factories ─────────────────────────────────────────────────────────

def _poverty_dataset(race_key: str, suffix: str, label: str) -> ACSDataset:
    t = f"B17001{suffix}"
    return ACSDataset(
        table_id=t,
        name=f"poverty_status_{race_key}",
        title=f"Poverty Status — {label}",
        description=f"Poverty status for {label} population in Baltimore City.",
        columns=[
            ColumnDef(f"{t}_001E", "poverty_universe",
                      f"Total {label} population with poverty status determined",
                      universe=label),
            ColumnDef(f"{t}_002E", "below_poverty",
                      f"{label} population with income below poverty level",
                      universe=label),
        ],
    )


def _income_dataset(race_key: str, suffix: str, label: str) -> ACSDataset:
    t = f"B19013{suffix}"
    return ACSDataset(
        table_id=t,
        name=f"median_hh_income_{race_key}",
        title=f"Median Household Income — {label}",
        description=(
            f"Median household income where the householder identifies as {label}. "
            "Inflation-adjusted to the ACS vintage year's dollars."
        ),
        columns=[
            ColumnDef(f"{t}_001E", "median_household_income",
                      f"Median household income ({label} householder, inflation-adjusted dollars)",
                      universe=f"{label} householder households",
                      notes="Race of householder, not race of all occupants."),
        ],
    )


def _tenure_dataset(race_key: str, suffix: str, label: str) -> ACSDataset:
    t = f"B25003{suffix}"
    return ACSDataset(
        table_id=t,
        name=f"housing_tenure_{race_key}",
        title=f"Housing Tenure — {label}",
        description=(
            f"Housing tenure for households with a {label} householder. "
            "Used to compute the homeownership rate by race."
        ),
        columns=[
            ColumnDef(f"{t}_001E", "total_occupied_units",
                      f"Total occupied units ({label} householder)",
                      universe=f"{label} householder households",
                      notes="Race of householder, not race of all occupants."),
            ColumnDef(f"{t}_002E", "owner_occupied",
                      f"Owner-occupied units ({label} householder)",
                      universe=f"{label} householder households"),
            ColumnDef(f"{t}_003E", "renter_occupied",
                      f"Renter-occupied units ({label} householder)",
                      universe=f"{label} householder households"),
        ],
    )


# ── Dataset instances ─────────────────────────────────────────────────────────

POVERTY_BY_RACE: dict[str, ACSDataset] = {
    key: _poverty_dataset(key, suffix, label)
    for key, (suffix, label) in RACE_GROUPS.items()
}

INCOME_BY_RACE: dict[str, ACSDataset] = {
    key: _income_dataset(key, suffix, label)
    for key, (suffix, label) in RACE_GROUPS.items()
}

TENURE_BY_RACE: dict[str, ACSDataset] = {
    key: _tenure_dataset(key, suffix, label)
    for key, (suffix, label) in RACE_GROUPS.items()
}

ALL_EQUITY_DATASETS: list[ACSDataset] = (
    list(POVERTY_BY_RACE.values())
    + list(INCOME_BY_RACE.values())
    + list(TENURE_BY_RACE.values())
)


# ── Pull function ─────────────────────────────────────────────────────────────

def pull_equity_dataset(dataset: ACSDataset, save: bool = True) -> pd.DataFrame:
    """Fetch one equity ACS dataset across all available 1-Year vintages.

    Reuses the same Census API client as the main factsheet pipeline.
    Rows where the Census returns None/suppressed values for the key variables
    are kept (as NaN) rather than dropped.
    """
    years = acs1_years(dataset.start_year)
    rows = []

    for year in years:
        try:
            raw = fetch_acs_city(dataset.variables, year)
        except Exception:
            # ACS 1-Year suppresses small-population geographies — skip silently
            continue

        save_raw_response(raw, "acs1", dataset.table_id, year, geo="city")

        headers = raw[0]
        row_data = raw[1]

        row: dict = {"year": year, "geography": "Baltimore City"}
        for header, value in zip(headers, row_data):
            col_name = dataset.rename_map.get(header)
            if col_name is None:
                continue
            row[col_name] = _to_numeric(value)

        rows.append(row)

    df = pd.DataFrame(rows)

    if save:
        save_dataset(df, dataset.file_name)

    return df


# ── Metric computation ────────────────────────────────────────────────────────

def _poverty_rate(row: pd.Series) -> float | None:
    universe = row.get("poverty_universe")
    below = row.get("below_poverty")
    if universe and universe > 0 and below is not None:
        return round(below / universe * 100, 2)
    return None


def _direct(col: str):
    def _compute(row: pd.Series) -> float | None:
        val = row.get(col)
        return float(val) if val is not None else None
    return _compute


def _homeownership_rate(row: pd.Series) -> float | None:
    total = row.get("total_occupied_units")
    owner = row.get("owner_occupied")
    if total and total > 0 and owner is not None:
        return round(owner / total * 100, 2)
    return None


_ACS1Y_SUPPRESSION_NOTE = (
    "ACS 1-Year estimates are suppressed by the Census Bureau when sub-group "
    "sample sizes are too small to produce statistically reliable figures. "
    "Suppressed values appear as blank in the output."
)

# Suppression notes per indicator per race group (only entries that differ from the base caveat)
_SUPPRESSION_OVERRIDES: dict[tuple[str, str], str] = {
    ("poverty_rate_{key}", "asian"): (
        "SUPPRESSED — Census ACS 1-Year does not publish poverty estimates for the Asian "
        "population in Baltimore City. The Asian sub-population (~13,000 people, ~2% of city) "
        "is too small for reliable single-year estimates; the B17001 table's detailed age/sex "
        "sub-categories further reduce cell sizes, triggering suppression. The Census API returns "
        "null for B17001D_001E and B17001D_002E for all years. "
        "ACS 5-Year estimates do have this data (e.g., ~21% poverty rate for 2019–2023). "
        + _ACS1Y_SUPPRESSION_NOTE
    ),
}

_BASE_EQUITY_CAVEATS = (
    "Race/ethnicity breakdowns use ACS 1-Year race-iteration tables. "
    "Values reflect the race of the householder (for income and homeownership) "
    "or the individual (for poverty), not the race of all household members. "
    + _ACS1Y_SUPPRESSION_NOTE
    + " 2020 ACS 1-Year was not released due to COVID data collection issues."
)

# Each entry: (id_template, indicator_name, source_table_base, compute_fn, dataset_dict, unit, formula_description)
_EQUITY_METRIC_SPECS = [
    (
        "poverty_rate_{key}",
        "Poverty Rate",
        "B17001",
        _poverty_rate,
        POVERTY_BY_RACE,
        "percent",
        "B17001{suffix}_002E (below poverty) / B17001{suffix}_001E (poverty universe) × 100",
    ),
    (
        "median_hh_income_{key}",
        "Median Household Income",
        "B19013",
        _direct("median_household_income"),
        INCOME_BY_RACE,
        "dollars",
        "Direct read of B19013{suffix}_001E (median household income, race-iteration table)",
    ),
    (
        "homeownership_rate_{key}",
        "Homeownership Rate",
        "B25003",
        _homeownership_rate,
        TENURE_BY_RACE,
        "percent",
        "B25003{suffix}_002E (owner-occupied) / B25003{suffix}_001E (total occupied units) × 100",
    ),
]


def compute_equity_metrics(equity_datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Compute all equity metrics from pulled datasets.

    Args:
        equity_datasets: Dict mapping dataset file_name → DataFrame,
                         as returned by pull_equity_dataset() for each dataset.

    Returns:
        DataFrame in EQUITY_OUTPUT_COLUMNS schema — one row per
        year × indicator × demographic_group.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = []

    for id_template, indicator_name, table_base, compute_fn, dataset_dict, unit, _ in _EQUITY_METRIC_SPECS:
        source_url = resolve_acs_vintage_tokens(f"{_ACS1Y_URL}.{table_base}")
        for race_key, (suffix, label) in RACE_GROUPS.items():
            dataset = dataset_dict[race_key]
            df = equity_datasets.get(dataset.file_name)
            if df is None:
                continue

            indicator_id = id_template.replace("{key}", race_key)

            for _, dataset_row in df.iterrows():
                value = compute_fn(dataset_row)
                rows.append({
                    "indicator_id": indicator_id,
                    "geography": dataset_row["geography"],
                    "indicator_name": indicator_name,
                    "demographic_group": label,
                    "value": value,
                    "margin_of_error": None,
                    "year": dataset_row["year"],
                    "period": str(dataset_row["year"]),
                    "source": _ACS_SOURCE,
                    "source_url": source_url,
                    "last_updated": now,
                })

    return pd.DataFrame(rows, columns=EQUITY_OUTPUT_COLUMNS)


def build_equity_methodology_table() -> pd.DataFrame:
    """Generate a methodology/caveats table for all equity indicators.

    Produces one row per indicator × demographic_group combination, documenting
    the formula, source table, and caveats — including Census suppression notes
    where applicable (e.g., Asian poverty rate is suppressed in ACS 1-Year).

    Returns:
        DataFrame with columns matching the equity methodology schema.
    """
    from datetime import date
    today = date.today().isoformat()
    rows = []

    for id_template, indicator_name, table_base, _, dataset_dict, unit, formula_template in _EQUITY_METRIC_SPECS:
        source_url = resolve_acs_vintage_tokens(f"{_ACS1Y_URL}.{table_base}")
        for race_key, (suffix, label) in RACE_GROUPS.items():
            indicator_id = id_template.replace("{key}", race_key)
            formula = formula_template.replace("{suffix}", suffix)
            source_table = f"{table_base}{suffix}"
            caveats = _SUPPRESSION_OVERRIDES.get((id_template, race_key), _BASE_EQUITY_CAVEATS)

            rows.append({
                "indicator_id": indicator_id,
                "indicator_name": indicator_name,
                "demographic_group": label,
                "source_table": source_table,
                "formula": formula,
                "source_name": _ACS_SOURCE,
                "source_url": source_url,
                "unit": unit,
                "update_frequency": "annual",
                "geographic_level": "city",
                "caveats": caveats,
                "last_verified": today,
            })

    return pd.DataFrame(rows)

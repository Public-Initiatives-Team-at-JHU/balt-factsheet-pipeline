from __future__ import annotations

"""
Dashboard metric definitions and computation.

Metrics are computed FROM clean datasets (Layer 2 → Layer 3). Each Metric
dataclass carries:
- A stable id for Power BI joins between data and methodology tables
- A compute function (DataFrame row → value)
- A plain-English formula description for non-technical users

The compute function and its documentation are co-located so you can't
update one without seeing the other.

Adding a new metric = adding a new Metric instance. No pipeline code changes.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Optional

import pandas as pd

from src.utils.config import DASHBOARD_COLUMNS, METHODOLOGY_COLUMNS


@dataclass
class Metric:
    """Declarative definition of a dashboard metric.

    The compute function takes a single DataFrame row (a pd.Series from the
    source dataset) and returns the metric value. It's documented alongside
    its formula so non-technical readers can understand the derivation.
    """

    id: str               # Stable identifier, e.g. "unemployment_rate_acs"
    name: str             # Display name, e.g. "Unemployment Rate"
    description: str      # What this metric measures
    compute: Callable     # (pd.Series) -> Optional[float]
    source_dataset: str   # Which clean dataset file name (e.g. "acs5_employment_status")
    source_table: str     # Census table ID (e.g. "B23025")
    formula_description: str  # Plain English formula
    source_name: str      # e.g. "ACS 5-Year Estimates"
    source_url: str       # Link to data.census.gov table
    unit: str             # "count", "percent", "dollars", "ratio"
    update_frequency: str  # "annual", "monthly", etc.
    geographic_level: str = "city"
    caveats: str = ""
    period_format: str = "1-year"  # How to label the period column


def compute_all_metrics(
    metrics: list,
    datasets: dict,
) -> pd.DataFrame:
    """Compute all metrics from their source datasets.

    Args:
        metrics: List of Metric definitions to compute
        datasets: Dict mapping dataset file names (e.g. "acs5_total_population")
                  to their clean DataFrames

    Returns:
        DataFrame in dashboard output schema — one row per metric per year.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = []

    for metric in metrics:
        df = datasets.get(metric.source_dataset)
        if df is None:
            raise KeyError(
                f"Metric '{metric.name}' requires dataset '{metric.source_dataset}' "
                f"but it was not provided. Available: {list(datasets.keys())}"
            )

        for _, dataset_row in df.iterrows():
            value = metric.compute(dataset_row)
            year = dataset_row["year"]

            if metric.period_format == "5-year":
                period = f"{year - 4}-{year}"
            else:
                period = str(year)

            rows.append({
                "indicator_id": metric.id,
                "geography": dataset_row["geography"],
                "indicator_name": metric.name,
                "value": round(value, 2) if value is not None else None,
                "margin_of_error": None,
                "year": year,
                "period": period,
                "source": metric.source_name,
                "source_url": metric.source_url,
                "last_updated": now,
            })

    return pd.DataFrame(rows, columns=DASHBOARD_COLUMNS)


def build_methodology_table(metrics: list) -> pd.DataFrame:
    """Generate the methodology documentation table.

    Each row documents one metric's formula, source, and caveats.
    Designed to import directly as a Microsoft List on SharePoint.

    Args:
        metrics: List of all Metric definitions

    Returns:
        DataFrame with methodology columns.
    """
    today = date.today().isoformat()
    rows = []
    for metric in metrics:
        rows.append({
            "indicator_id": metric.id,
            "indicator_name": metric.name,
            "description": metric.description,
            "formula": metric.formula_description,
            "source_name": metric.source_name,
            "source_table": metric.source_table,
            "source_dataset": metric.source_dataset,
            "source_url": metric.source_url,
            "unit": metric.unit,
            "update_frequency": metric.update_frequency,
            "geographic_level": metric.geographic_level,
            "caveats": metric.caveats,
            "last_verified": today,
        })
    return pd.DataFrame(rows, columns=METHODOLOGY_COLUMNS)


# ── Metric Definitions ───────────────────────────────────────────────────────

TOTAL_POPULATION_METRIC = Metric(
    id="total_population",
    name="Total Population",
    description="Total population of Baltimore City",
    compute=lambda row: row["total_population"],
    source_dataset="acs1_total_population",
    source_table="B01003",
    formula_description="Direct read of B01003_001E (total population estimate)",
    source_name="ACS 1-Year Estimates",
    source_url="https://data.census.gov/table/ACSDT1Y2023.B01003",
    unit="count",
    update_frequency="annual",
    caveats=(
        "ACS 1-year estimates represent a single calendar year. "
        "2020 ACS 1-Year was not released due to COVID data collection issues."
    ),
)

MEDIAN_HOUSEHOLD_INCOME_METRIC = Metric(
    id="median_hh_income",
    name="Median Household Income",
    description="Median household income in the past 12 months (inflation-adjusted dollars)",
    compute=lambda row: row["median_household_income"],
    source_dataset="acs1_median_household_income",
    source_table="B19013",
    formula_description="Direct read of B19013_001E (median household income)",
    source_name="ACS 1-Year Estimates",
    source_url="https://data.census.gov/table/ACSDT1Y2023.B19013",
    unit="dollars",
    update_frequency="annual",
    caveats=(
        "Each vintage is inflation-adjusted to that year's dollars. "
        "Comparing across years without adjusting for inflation is misleading. "
        "MOE provided by Census."
    ),
)

UNEMPLOYMENT_RATE_METRIC = Metric(
    id="unemployment_rate_acs",
    name="Unemployment Rate",
    description="Percentage of civilian labor force that is unemployed",
    compute=lambda row: (
        row["unemployed"] / row["civilian_labor_force"] * 100
        if row["civilian_labor_force"] and row["civilian_labor_force"] > 0
        else None
    ),
    source_dataset="acs1_employment_status",
    source_table="B23025",
    formula_description=(
        "B23025_005E (unemployed) / B23025_003E (civilian labor force) × 100"
    ),
    source_name="ACS 1-Year Estimates",
    source_url="https://data.census.gov/table/ACSDT1Y2023.B23025",
    unit="percent",
    update_frequency="annual",
    caveats=(
        "ACS unemployment differs from BLS LAUS methodology. "
        "ACS uses annual survey estimates; BLS uses monthly household surveys. "
        "BLS LAUS is the more commonly cited source for monthly unemployment."
    ),
)

BACHELORS_PLUS_METRIC = Metric(
    id="bachelors_degree_plus",
    name="Bachelor's Degree or Higher (%)",
    description="Percentage of population 25+ with a Bachelor's degree or higher",
    compute=lambda row: (
        (row["bachelors_degree"] + row["masters_degree"]
         + row["professional_degree"] + row["doctorate_degree"])
        / row["pop_25_and_over"] * 100
        if row["pop_25_and_over"] and row["pop_25_and_over"] > 0
        else None
    ),
    source_dataset="acs1_education_attainment",
    source_table="B15003",
    formula_description=(
        "(B15003_022E + _023E + _024E + _025E) / B15003_001E × 100. "
        "Numerator = Bachelor's + Master's + Professional + Doctorate."
    ),
    source_name="ACS 1-Year Estimates",
    source_url="https://data.census.gov/table/ACSDT1Y2023.B15003",
    unit="percent",
    update_frequency="annual",
)

LESS_THAN_HS_METRIC = Metric(
    id="less_than_hs_diploma",
    name="Less Than High School Diploma (%)",
    description="Percentage of population 25+ with less than a high school diploma",
    compute=lambda row: (
        (row["no_schooling"] + row["nursery_school"] + row["kindergarten"]
         + row["grade_1"] + row["grade_2"] + row["grade_3"]
         + row["grade_4"] + row["grade_5"] + row["grade_6"]
         + row["grade_7"] + row["grade_8"] + row["grade_9"]
         + row["grade_10"] + row["grade_11"] + row["grade_12_no_diploma"])
        / row["pop_25_and_over"] * 100
        if row["pop_25_and_over"] and row["pop_25_and_over"] > 0
        else None
    ),
    source_dataset="acs1_education_attainment",
    source_table="B15003",
    formula_description=(
        "Sum(B15003_002E through _016E) / B15003_001E × 100. "
        "Numerator = all categories below 'Regular high school diploma' "
        "(no schooling through 12th grade, no diploma)."
    ),
    source_name="ACS 1-Year Estimates",
    source_url="https://data.census.gov/table/ACSDT1Y2023.B15003",
    unit="percent",
    update_frequency="annual",
)

MORTGAGE_COST_BURDEN_METRIC = Metric(
    id="mortgage_cost_burden_30pct",
    name="Mortgage Cost Burden (30%+ of Income)",
    description=(
        "Percentage of homeowners with a mortgage who spend 30% or more "
        "of household income on housing costs"
    ),
    compute=lambda row: (
        (row["pct_30_to_34_9"] + row["pct_35_to_39_9"]
         + row["pct_40_to_49_9"] + row["pct_50_or_more"])
        / row["computed_total"] * 100
        if row["computed_total"] and row["computed_total"] > 0
        else None
    ),
    source_dataset="acs1_mortgage_costs",
    source_table="B25091",
    formula_description=(
        "(B25091_008E + _009E + _010E + _011E) / B25091_002E × 100. "
        "Numerator = units paying 30%+ of income. "
        "Denominator = units with computed cost ratio (excludes zero/negative income)."
    ),
    source_name="ACS 1-Year Estimates",
    source_url="https://data.census.gov/table/ACSDT1Y2023.B25091",
    unit="percent",
    update_frequency="annual",
    caveats="Only includes owner-occupied units with a mortgage, not outright owners.",
)

RENT_COST_BURDEN_METRIC = Metric(
    id="rent_cost_burden_30pct",
    name="Rent Cost Burden (30%+ of Income)",
    description=(
        "Percentage of renters who spend 30% or more "
        "of household income on gross rent"
    ),
    compute=lambda row: (
        (row["pct_30_to_34_9"] + row["pct_35_to_39_9"]
         + row["pct_40_to_49_9"] + row["pct_50_or_more"])
        / (row["total_renters"] - row["not_computed"]) * 100
        if (row["total_renters"] and row["not_computed"] is not None
            and (row["total_renters"] - row["not_computed"]) > 0)
        else None
    ),
    source_dataset="acs1_rent_costs",
    source_table="B25070",
    formula_description=(
        "(B25070_007E + _008E + _009E + _010E) / (B25070_001E - B25070_011E) × 100. "
        "Numerator = renters paying 30%+ of income. "
        "Denominator = total renters minus 'not computed' "
        "(excludes zero/negative income and no-cash-rent units)."
    ),
    source_name="ACS 1-Year Estimates",
    source_url="https://data.census.gov/table/ACSDT1Y2023.B25070",
    unit="percent",
    update_frequency="annual",
    caveats="Excludes no-cash-rent units and zero/negative income households from denominator.",
)

AVG_HOUSEHOLD_SIZE_METRIC = Metric(
    id="avg_household_size",
    name="Average Household Size",
    description="Average number of persons per occupied housing unit",
    compute=lambda row: row["avg_household_size"],
    source_dataset="acs1_household_size",
    source_table="B25010",
    formula_description="Direct read of B25010_001E (average household size of occupied units)",
    source_name="ACS 1-Year Estimates",
    source_url="https://data.census.gov/table/ACSDT1Y2023.B25010",
    unit="ratio",
    update_frequency="annual",
)


ALL_FACTSHEET_METRICS = [
    TOTAL_POPULATION_METRIC,
    MEDIAN_HOUSEHOLD_INCOME_METRIC,
    UNEMPLOYMENT_RATE_METRIC,
    BACHELORS_PLUS_METRIC,
    LESS_THAN_HS_METRIC,
    MORTGAGE_COST_BURDEN_METRIC,
    RENT_COST_BURDEN_METRIC,
    AVG_HOUSEHOLD_SIZE_METRIC,
]

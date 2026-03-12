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
            print(
                f"  WARNING: skipping '{metric.name}' — "
                f"dataset '{metric.source_dataset}' not available"
            )
            continue

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


def pivot_to_wide(long_df: pd.DataFrame, metrics: list) -> pd.DataFrame:
    """Pivot long-format fact sheet to wide format for Excel/SharePoint.

    Args:
        long_df: Long-format DataFrame from compute_all_metrics()
        metrics: Ordered list of Metric definitions (sets column order)

    Returns:
        Wide DataFrame — one row per year, one column per metric.
        Column names are human-readable indicator names.
        NaN where a metric has no data for a given year (e.g. ACS missing 2020,
        PEP only starting 2020).
    """
    # Pivot on indicator_id (stable), then rename to human-readable names
    wide = long_df.pivot_table(
        index="year",
        columns="indicator_id",
        values="value",
        aggfunc="first",
    ).reset_index()

    # Rename columns from indicator_id → indicator_name
    id_to_name = {m.id: m.name for m in metrics}
    wide = wide.rename(columns=id_to_name)

    # Ensure all metrics appear even when every value for a metric is None
    # (pivot_table drops all-NaN columns, but we want explicit NaN columns)
    for m in metrics:
        if m.name not in wide.columns:
            wide[m.name] = float("nan")

    # Enforce column order: year first, then metrics in definition order
    ordered_names = [m.name for m in metrics]
    wide = wide[["year"] + ordered_names]

    return wide.sort_values("year").reset_index(drop=True)


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

UNEMPLOYMENT_RATE_BLS_METRIC = Metric(
    id="unemployment_rate_bls",
    name="Unemployment Rate",
    description="Percentage of civilian labor force that is unemployed (annual average)",
    compute=lambda row: row["annual_unemployment_rate"],
    source_dataset="bls_laus_unemployment",
    source_table="LAUS",
    formula_description=(
        "Annual average of BLS LAUS monthly unemployment rates. "
        "Series ID: LAUCN245100000000003 (Baltimore City, not seasonally adjusted)."
    ),
    source_name="BLS Local Area Unemployment Statistics",
    source_url="https://www.bls.gov/lau/",
    unit="percent",
    update_frequency="monthly (aggregated to annual)",
    caveats=(
        "Monthly estimates are not seasonally adjusted. "
        "Annual value is the arithmetic mean of 12 monthly observations. "
        "BLS LAUS is the authoritative source for unemployment rates."
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


POPULATION_PEP_METRIC = Metric(
    id="total_population_pep",
    name="Total Population (Official Estimate)",
    description=(
        "Official Census Bureau annual population estimate (July 1). "
        "Model-based, combining Census count with births, deaths, and migration data."
    ),
    compute=lambda row: row["population_estimate"],
    source_dataset="pep_population",
    source_table="PEP",
    formula_description="Direct read of POPESTIMATE (July 1 annual estimate).",
    source_name="Census Population Estimates Program",
    source_url="https://www.census.gov/programs-surveys/popest.html",
    unit="count",
    update_frequency="annual",
    caveats=(
        "Covers 2020–present (2020-base series). "
        "Earlier years use a separate pre-2020 series. "
        "Estimates are revised in subsequent vintage years."
    ),
)

POVERTY_RATE_METRIC = Metric(
    id="poverty_rate",
    name="Poverty Rate",
    description="Percentage of residents with income below the federal poverty level",
    compute=lambda row: (
        row["below_poverty"] / row["poverty_universe"] * 100
        if row["poverty_universe"] and row["poverty_universe"] > 0
        else None
    ),
    source_dataset="acs1_poverty_status",
    source_table="B17001",
    formula_description=(
        "B17001_002E (below poverty) / B17001_001E (poverty universe) × 100. "
        "Universe excludes institutionalized people and others for whom "
        "poverty status is not determined."
    ),
    source_name="ACS 1-Year Estimates",
    source_url="https://data.census.gov/table/ACSDT1Y2023.B17001",
    unit="percent",
    update_frequency="annual",
    caveats=(
        "Uses the federal poverty thresholds, which are widely considered to "
        "underestimate true economic hardship. Universe excludes ~2% of population "
        "for whom poverty status is not determined."
    ),
)

HOMEOWNERSHIP_RATE_METRIC = Metric(
    id="homeownership_rate",
    name="Homeownership Rate",
    description="Percentage of occupied housing units that are owner-occupied",
    compute=lambda row: (
        row["owner_occupied"] / row["total_occupied_units"] * 100
        if row["total_occupied_units"] and row["total_occupied_units"] > 0
        else None
    ),
    source_dataset="acs1_housing_tenure",
    source_table="B25003",
    formula_description=(
        "B25003_002E (owner-occupied) / B25003_001E (total occupied units) × 100."
    ),
    source_name="ACS 1-Year Estimates",
    source_url="https://data.census.gov/table/ACSDT1Y2023.B25003",
    unit="percent",
    update_frequency="annual",
)

VACANCY_RATE_METRIC = Metric(
    id="housing_vacancy_rate",
    name="Housing Vacancy Rate",
    description="Percentage of housing units that are vacant",
    compute=lambda row: (
        row["vacant_units"] / row["total_housing_units"] * 100
        if row["total_housing_units"] and row["total_housing_units"] > 0
        else None
    ),
    source_dataset="acs1_housing_occupancy",
    source_table="B25002",
    formula_description=(
        "B25002_003E (vacant units) / B25002_001E (total housing units) × 100."
    ),
    source_name="ACS 1-Year Estimates",
    source_url="https://data.census.gov/table/ACSDT1Y2023.B25002",
    unit="percent",
    update_frequency="annual",
    caveats=(
        "ACS vacancy counts all vacant units including seasonal/recreational. "
        "Does not distinguish between structurally vacant (blight) and "
        "temporarily unoccupied units. For Baltimore's blight context, "
        "Open Baltimore's DHCD vacant building registry is more precise."
    ),
)


_RACE_URL = "https://data.census.gov/table/ACSDT1Y2023.B03002"
_RACE_SOURCE = "ACS 1-Year Estimates"
_RACE_CAVEATS = (
    "Race/ethnicity categories follow Census definitions. "
    "Hispanic/Latino is an origin category that spans all races; "
    "all non-Hispanic categories are mutually exclusive. "
    "AIAN, NHPI, other race, and two-or-more-races groups are small "
    "in Baltimore and have higher sampling error."
)


def _race_pct(numerator_col: str):
    """Return a compute function for % of total population."""
    def _compute(row):
        total = row["total_population"]
        if total and total > 0:
            return row[numerator_col] / total * 100
        return None
    return _compute


PCT_WHITE_METRIC = Metric(
    id="pct_white_non_hispanic",
    name="White (Non-Hispanic) (%)",
    description="Percentage of population identifying as White alone, non-Hispanic",
    compute=_race_pct("white_non_hispanic"),
    source_dataset="acs1_race_ethnicity",
    source_table="B03002",
    formula_description="B03002_003E / B03002_001E × 100",
    source_name=_RACE_SOURCE,
    source_url=_RACE_URL,
    unit="percent",
    update_frequency="annual",
    caveats=_RACE_CAVEATS,
)

PCT_BLACK_METRIC = Metric(
    id="pct_black_non_hispanic",
    name="Black or African American (Non-Hispanic) (%)",
    description="Percentage of population identifying as Black or African American alone, non-Hispanic",
    compute=_race_pct("black_non_hispanic"),
    source_dataset="acs1_race_ethnicity",
    source_table="B03002",
    formula_description="B03002_004E / B03002_001E × 100",
    source_name=_RACE_SOURCE,
    source_url=_RACE_URL,
    unit="percent",
    update_frequency="annual",
    caveats=_RACE_CAVEATS,
)

PCT_HISPANIC_METRIC = Metric(
    id="pct_hispanic_latino",
    name="Hispanic or Latino (%)",
    description="Percentage of population identifying as Hispanic or Latino (of any race)",
    compute=_race_pct("hispanic_latino"),
    source_dataset="acs1_race_ethnicity",
    source_table="B03002",
    formula_description="B03002_012E / B03002_001E × 100",
    source_name=_RACE_SOURCE,
    source_url=_RACE_URL,
    unit="percent",
    update_frequency="annual",
    caveats=_RACE_CAVEATS,
)

PCT_ASIAN_METRIC = Metric(
    id="pct_asian_non_hispanic",
    name="Asian (Non-Hispanic) (%)",
    description="Percentage of population identifying as Asian alone, non-Hispanic",
    compute=_race_pct("asian_non_hispanic"),
    source_dataset="acs1_race_ethnicity",
    source_table="B03002",
    formula_description="B03002_006E / B03002_001E × 100",
    source_name=_RACE_SOURCE,
    source_url=_RACE_URL,
    unit="percent",
    update_frequency="annual",
    caveats=_RACE_CAVEATS,
)

PCT_TWO_OR_MORE_METRIC = Metric(
    id="pct_two_or_more_races",
    name="Two or More Races (Non-Hispanic) (%)",
    description="Percentage of population identifying as two or more races, non-Hispanic",
    compute=_race_pct("two_or_more_non_hispanic"),
    source_dataset="acs1_race_ethnicity",
    source_table="B03002",
    formula_description="B03002_009E / B03002_001E × 100",
    source_name=_RACE_SOURCE,
    source_url=_RACE_URL,
    unit="percent",
    update_frequency="annual",
    caveats=_RACE_CAVEATS,
)

PCT_OTHER_RACE_METRIC = Metric(
    id="pct_other_race_non_hispanic",
    name="Other Race (Non-Hispanic) (%)",
    description=(
        "Percentage of population identifying as AIAN, NHPI, some other race, "
        "or two or more races — all non-Hispanic. Grouped due to small cell sizes."
    ),
    compute=lambda row: (
        (row["aian_non_hispanic"] + row["nhpi_non_hispanic"]
         + row["other_race_non_hispanic"] + row["two_or_more_non_hispanic"])
        / row["total_population"] * 100
        if row["total_population"] and row["total_population"] > 0
        else None
    ),
    source_dataset="acs1_race_ethnicity",
    source_table="B03002",
    formula_description=(
        "(B03002_005E + B03002_007E + B03002_008E + B03002_009E) / B03002_001E × 100. "
        "Combines AIAN, NHPI, other race, and two-or-more-races (all non-Hispanic)."
    ),
    source_name=_RACE_SOURCE,
    source_url=_RACE_URL,
    unit="percent",
    update_frequency="annual",
    caveats=_RACE_CAVEATS,
)


_BPD_CAVEATS = (
    "Source: BPD Part 1 Victim Based Crime Data (wsfq-mvij). "
    "⚠️ Data quality issues from May 2021 due to BPD Records Management System "
    "transition — 2021 and 2022 annual totals are likely understated. "
    "Rate denominator is ACS 1-Year total population estimate."
)
_BPD_URL = "https://data.baltimorecity.gov/Public-Safety/BPD-Part-1-Victim-Based-Crime-Data/wsfq-mvij"
_BPD_SOURCE = "BPD Part 1 Victim Based Crime Data / Open Baltimore"


def _crime_rate(col: str):
    """Return a compute function for a pre-computed per-1,000 crime rate."""
    def _compute(row):
        val = row.get(col)
        return float(val) if val is not None and not (isinstance(val, float) and val != val) else None
    return _compute


PART1_CRIME_RATE_METRIC = Metric(
    id="part1_crime_rate_per_1k",
    name="Part 1 Crime Rate (per 1,000)",
    description="Total FBI UCR Part 1 crimes per 1,000 residents",
    compute=_crime_rate("part1_rate_per_1k"),
    source_dataset="ob_crime_rates",
    source_table="BPD Part 1 (wsfq-mvij)",
    formula_description=(
        "Annual Part 1 crime incident count / ACS total population × 1,000. "
        "Part 1 crimes = violent + property (see violent/property metrics)."
    ),
    source_name=_BPD_SOURCE,
    source_url=_BPD_URL,
    unit="rate per 1,000",
    update_frequency="annual",
    caveats=_BPD_CAVEATS,
)

VIOLENT_CRIME_RATE_METRIC = Metric(
    id="violent_crime_rate_per_1k",
    name="Violent Crime Rate (per 1,000)",
    description="Violent crimes per 1,000 residents (homicide, rape, robbery, aggravated assault)",
    compute=_crime_rate("violent_rate_per_1k"),
    source_dataset="ob_crime_rates",
    source_table="BPD Part 1 (wsfq-mvij)",
    formula_description=(
        "Annual violent crime count / ACS total population × 1,000. "
        "Violent = HOMICIDE + RAPE + ROBBERY (all types) + AGG. ASSAULT + SHOOTING."
    ),
    source_name=_BPD_SOURCE,
    source_url=_BPD_URL,
    unit="rate per 1,000",
    update_frequency="annual",
    caveats=_BPD_CAVEATS,
)

PROPERTY_CRIME_RATE_METRIC = Metric(
    id="property_crime_rate_per_1k",
    name="Property Crime Rate (per 1,000)",
    description="Property crimes per 1,000 residents (burglary, larceny, auto theft, arson)",
    compute=_crime_rate("property_rate_per_1k"),
    source_dataset="ob_crime_rates",
    source_table="BPD Part 1 (wsfq-mvij)",
    formula_description=(
        "Annual property crime count / ACS total population × 1,000. "
        "Property = BURGLARY + LARCENY + LARCENY FROM AUTO + AUTO THEFT + ARSON."
    ),
    source_name=_BPD_SOURCE,
    source_url=_BPD_URL,
    unit="rate per 1,000",
    update_frequency="annual",
    caveats=_BPD_CAVEATS,
)

HOMICIDE_COUNT_METRIC = Metric(
    id="homicide_count",
    name="Homicides (count)",
    description="Total homicide incidents reported to BPD",
    compute=lambda row: row.get("homicide_count"),
    source_dataset="ob_crime_rates",
    source_table="BPD Part 1 (wsfq-mvij)",
    formula_description="Direct count of incidents where Description = 'HOMICIDE'.",
    source_name=_BPD_SOURCE,
    source_url=_BPD_URL,
    unit="count",
    update_frequency="annual",
    caveats=_BPD_CAVEATS,
)


ALL_FACTSHEET_METRICS = [
    # Population
    TOTAL_POPULATION_METRIC,       # ACS 1-Year — long trend 2005–present
    # Economic
    MEDIAN_HOUSEHOLD_INCOME_METRIC,
    UNEMPLOYMENT_RATE_BLS_METRIC,
    POVERTY_RATE_METRIC,
    # Education
    BACHELORS_PLUS_METRIC,
    LESS_THAN_HS_METRIC,
    # Housing
    MORTGAGE_COST_BURDEN_METRIC,
    RENT_COST_BURDEN_METRIC,
    HOMEOWNERSHIP_RATE_METRIC,
    VACANCY_RATE_METRIC,
    # Demographics
    PCT_WHITE_METRIC,
    PCT_BLACK_METRIC,
    PCT_HISPANIC_METRIC,
    PCT_ASIAN_METRIC,
    PCT_TWO_OR_MORE_METRIC,
    PCT_OTHER_RACE_METRIC,
    # Crime
    PART1_CRIME_RATE_METRIC,
    VIOLENT_CRIME_RATE_METRIC,
    PROPERTY_CRIME_RATE_METRIC,
    HOMICIDE_COUNT_METRIC,
    # Household
    AVG_HOUSEHOLD_SIZE_METRIC,
]

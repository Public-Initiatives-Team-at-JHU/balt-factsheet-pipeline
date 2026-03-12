from __future__ import annotations

"""
Clean dataset definitions and processing for Census ACS tables.

This module defines the ACSDataset dataclass — a declarative way to specify
which Census variables to pull, how to rename them, and what each column means.
Adding a new dataset is adding data, not writing pipeline code.

The pull_and_clean_dataset() function fetches data across multiple years,
renames columns to human-readable names, and produces a clean DataFrame
ready for analysis or metric computation.
"""

from dataclasses import dataclass, field

import pandas as pd

import numpy as np

from src.pipelines.census_acs import fetch_acs_city
from src.pipelines.census_pop import fetch_pep_population, parse_pep_year
from src.pipelines.open_baltimore import (
    BPD_DATA_QUALITY_ISSUE_YEAR,
    classify_crime,
    fetch_crime_counts_by_year,
)
from src.utils.config import ACS1_EARLIEST_YEAR, ACS1_LATEST_YEAR, PEP_LATEST_VINTAGE, PEP_START_YEAR, acs1_years
from src.utils.io import save_data_dictionary, save_dataset, save_raw_response

# Census uses this sentinel for suppressed margins of error
CENSUS_SUPPRESSED_MOE = -555555555


@dataclass
class ColumnDef:
    """Definition of a single column in a clean dataset."""

    census_variable: str  # e.g. "B01003_001E"
    name: str             # Human-readable column name
    description: str      # What this variable means
    universe: str = ""    # Census "universe" (population this applies to)
    notes: str = ""       # Caveats or special handling


@dataclass
class ACSDataset:
    """Declarative definition of a clean dataset built from a Census ACS table.

    Each instance defines:
    - Which Census table and variables to fetch
    - Human-readable column names and descriptions
    - Metadata for the auto-generated data dictionary
    """

    table_id: str       # e.g. "B01003"
    name: str           # Short name for file naming, e.g. "total_population"
    title: str          # Human-readable title, e.g. "Total Population"
    description: str    # What this dataset covers
    columns: list = field(default_factory=list)  # List[ColumnDef]
    start_year: int = ACS1_EARLIEST_YEAR  # First year this table is available in ACS 1-Year

    @property
    def file_name(self) -> str:
        """Dataset file name without extension. Prefixed with acs1_."""
        return f"acs1_{self.name}"

    @property
    def variables(self) -> list:
        """Census variable codes to fetch."""
        return [col.census_variable for col in self.columns]

    @property
    def rename_map(self) -> dict:
        """Mapping from Census variable codes to human-readable column names."""
        return {col.census_variable: col.name for col in self.columns}

    @property
    def data_dictionary_rows(self) -> list:
        """Data dictionary entries for all columns (including non-Census ones)."""
        rows = [
            {
                "column": "year",
                "description": "ACS 5-Year vintage year (e.g. 2023 = 2019-2023 estimates)",
                "census_variable": "",
                "universe": "",
                "notes": "",
            },
            {
                "column": "geography",
                "description": "Geographic area name",
                "census_variable": "",
                "universe": "",
                "notes": "Baltimore City for city-level data",
            },
        ]
        for col in self.columns:
            rows.append(
                {
                    "column": col.name,
                    "description": col.description,
                    "census_variable": col.census_variable,
                    "universe": col.universe,
                    "notes": col.notes,
                }
            )
        return rows


def pull_and_clean_dataset(
    dataset: ACSDataset,
    years: list = None,
    save: bool = True,
) -> pd.DataFrame:
    """Fetch Census ACS data, clean it, and optionally save to disk.

    For each year:
    1. Calls the Census API for the dataset's variables
    2. Saves the raw JSON response (Layer 1)
    3. Renames columns from Census codes to human-readable names
    4. Converts types (strings → numeric, suppressed MOE sentinel → NaN)
    5. Assembles into a single DataFrame across all years

    Args:
        dataset: ACSDataset definition specifying what to pull
        years: List of ACS vintage years to fetch (default: ACS_YEARS from config)
        save: If True, save the clean CSV and data dictionary to data/datasets/

    Returns:
        Clean DataFrame with columns: year, geography, plus human-readable names.
    """
    if years is None:
        years = acs1_years(dataset.start_year)

    all_rows = []

    for year in years:
        raw = fetch_acs_city(dataset.variables, year)

        # Layer 1: save raw API response
        save_raw_response(raw, "acs5", dataset.table_id, year, geo="city")

        # raw[0] = headers, raw[1] = data row (city-level = single row)
        headers = raw[0]
        row_data = raw[1]

        # Build a dict for this year's data
        row = {"year": year, "geography": "Baltimore City"}
        for header, value in zip(headers, row_data):
            col_name = dataset.rename_map.get(header)
            if col_name is None:
                # Skip geography columns (state, county) returned by Census API
                continue
            numeric_val = _to_numeric(value)
            # Convert Census suppressed-MOE sentinel to NaN
            if numeric_val == CENSUS_SUPPRESSED_MOE:
                numeric_val = None
            row[col_name] = numeric_val

        all_rows.append(row)

    df = pd.DataFrame(all_rows)

    if save:
        save_dataset(df, dataset.file_name)
        save_data_dictionary(dataset.data_dictionary_rows, dataset.file_name)

    return df


def _to_numeric(value):
    """Convert a Census API string value to a number.

    Census returns everything as strings. Handles:
    - Integers: "577193" → 577193
    - Floats: "2.45" → 2.45
    - Nulls/missing: None, "" → None
    - Negative values (MOE sentinels): "-555555555" → -555555555
    """
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return None


# ── BLS LAUS Dataset ─────────────────────────────────────────────────────────


@dataclass
class BLSDataset:
    """Declarative definition for a BLS LAUS dataset.

    Similar to ACSDataset but for BLS Local Area Unemployment Statistics.
    """

    series_id: str      # e.g. "LAUST245100000000003"
    name: str           # Short name for file naming
    title: str          # Human-readable title
    description: str    # What this dataset covers
    measure: str        # What this measures (e.g., "unemployment_rate")
    start_year: int = 2005

    @property
    def file_name(self) -> str:
        """Dataset file name without extension. Prefixed with bls_."""
        return f"bls_{self.name}"

    @property
    def data_dictionary_rows(self) -> list:
        """Data dictionary entries for all columns."""
        return [
            {
                "column": "year",
                "description": "Calendar year",
                "bls_series": self.series_id,
                "notes": "",
            },
            {
                "column": "geography",
                "description": "Geographic area name",
                "bls_series": "",
                "notes": "Baltimore City for city-level data",
            },
            {
                "column": "month",
                "description": "Month number (1-12)",
                "bls_series": "",
                "notes": "Calendar month (1=January)",
            },
            {
                "column": f"monthly_{self.measure}",
                "description": f"Monthly {self.measure.replace('_', ' ')} (%)",
                "bls_series": self.series_id,
                "notes": "Not seasonally adjusted",
            },
            {
                "column": f"annual_{self.measure}",
                "description": f"Annual average {self.measure.replace('_', ' ')} (%)",
                "bls_series": "",
                "notes": "Mean of 12 monthly observations",
            },
        ]


def pull_and_clean_bls_dataset(
    dataset: BLSDataset,
    save: bool = True,
) -> pd.DataFrame:
    """Fetch BLS LAUS data, clean it, and optionally save to disk.

    Process:
    1. Calls the BLS API for monthly data
    2. Saves the raw JSON response (Layer 1)
    3. Parses monthly data points
    4. Converts string values to numeric
    5. Computes annual averages (mean of 12 monthly values)
    6. Assembles into a DataFrame with both monthly and annual data

    Args:
        dataset: BLSDataset definition specifying what to pull
        save: If True, save the clean CSV and data dictionary

    Returns:
        Clean DataFrame with columns: year, geography, month,
        monthly_{measure}, annual_{measure}
    """
    from src.pipelines.bls import fetch_bls_laus
    from datetime import datetime

    # BLS publishes data through current month, use current year
    end_year = datetime.now().year
    raw = fetch_bls_laus(dataset.series_id, dataset.start_year, end_year)

    # Layer 1: save raw API response
    save_raw_response(
        raw, "bls", "LAUS", f"{dataset.start_year}-{end_year}", geo="city"
    )

    # Parse monthly data points
    series_data = raw["Results"]["series"][0]["data"]

    rows = []
    for point in series_data:
        year = int(point["year"])
        period = point["period"]

        # Skip annual averages (period="M13") — we compute our own
        if period == "M13":
            continue

        # Extract month number from period (e.g. "M01" → 1)
        month = int(period.replace("M", ""))

        # BLS returns values as strings
        value = _to_numeric(point["value"])

        rows.append({
            "year": year,
            "geography": "Baltimore City",
            "month": month,
            f"monthly_{dataset.measure}": value,
        })

    monthly_df = pd.DataFrame(rows)

    # Compute annual averages (mean of 12 monthly values per year)
    annual_df = (
        monthly_df.groupby("year")[f"monthly_{dataset.measure}"]
        .mean()
        .reset_index()
        .rename(columns={f"monthly_{dataset.measure}": f"annual_{dataset.measure}"})
    )

    # Add geography column
    annual_df["geography"] = "Baltimore City"

    # Reorder columns
    annual_df = annual_df[["year", "geography", f"annual_{dataset.measure}"]]

    # Sort by year
    annual_df = annual_df.sort_values("year").reset_index(drop=True)

    if save:
        # Save annual aggregated data (for metric computation)
        save_dataset(annual_df, dataset.file_name)
        # Also save monthly data with _monthly suffix (for reference/future use)
        monthly_full = monthly_df.merge(
            annual_df[["year", f"annual_{dataset.measure}"]],
            on="year",
            how="left"
        ).sort_values(["year", "month"])
        save_dataset(monthly_full, f"{dataset.file_name}_monthly")
        # Save data dictionary
        save_data_dictionary(dataset.data_dictionary_rows, dataset.file_name)

    return annual_df


# ── Census PEP Dataset ────────────────────────────────────────────────────────


@dataclass
class PEPDataset:
    """Declarative definition for a Census PEP population dataset.

    PEP differs from ACS: a single vintage call returns all years via
    DATE_CODE, so there's no per-year loop. We always pull the latest
    vintage and extract each year's July 1 estimate.
    """

    name: str           # Short name for file naming
    title: str          # Human-readable title
    description: str    # What this dataset covers
    vintage_year: int = PEP_LATEST_VINTAGE

    @property
    def file_name(self) -> str:
        """Dataset file name without extension. Prefixed with pep_."""
        return f"pep_{self.name}"

    @property
    def data_dictionary_rows(self) -> list:
        return [
            {
                "column": "year",
                "description": "Calendar year of the July 1 population estimate",
                "census_variable": "DATE_DESC",
                "notes": "Parsed from DATE_DESC. Excludes April 2020 Census base.",
            },
            {
                "column": "geography",
                "description": "Geographic area name",
                "census_variable": "NAME",
                "notes": "Baltimore City",
            },
            {
                "column": "population_estimate",
                "description": "Official Census Bureau annual population estimate (July 1)",
                "census_variable": "POPESTIMATE",
                "notes": (
                    "Model-based estimate combining Census count with births, "
                    "deaths, and net migration. More accurate than ACS for point-in-time "
                    "population. Revised in subsequent vintages."
                ),
            },
        ]


def pull_and_clean_pep_dataset(
    dataset: PEPDataset,
    save: bool = True,
) -> pd.DataFrame:
    """Fetch Census PEP population data, clean it, and optionally save to disk.

    Process:
    1. Calls the PEP API for the latest vintage (returns all years in one call)
    2. Saves the raw JSON response (Layer 1)
    3. Filters to July 1 annual estimates (excludes April 2020 Census base)
    4. Parses year from DATE_DESC
    5. Assembles into a clean DataFrame

    Args:
        dataset: PEPDataset definition
        save: If True, save the clean CSV and data dictionary

    Returns:
        Clean DataFrame with columns: year, geography, population_estimate
    """
    raw = fetch_pep_population(dataset.vintage_year)

    # Layer 1: save raw API response
    save_raw_response(
        raw, "pep", "population", f"{PEP_START_YEAR}-{dataset.vintage_year}", geo="city"
    )

    # raw[0] = headers, raw[1:] = one row per DATE_CODE
    headers = raw[0]
    col = {h: i for i, h in enumerate(headers)}

    rows = []
    for row in raw[1:]:
        date_desc = row[col["DATE_DESC"]]
        year = parse_pep_year(date_desc)

        # Skip the April 2020 Census base (not a July 1 estimate)
        if year is None or "estimates base" in date_desc.lower():
            continue

        # Only include years within our intended range
        if year < PEP_START_YEAR:
            continue

        pop = _to_numeric(row[col["POPESTIMATE"]])
        name = row[col["NAME"]]

        rows.append({
            "year": year,
            "geography": name,
            "population_estimate": pop,
        })

    df = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)

    if save:
        save_dataset(df, dataset.file_name)
        save_data_dictionary(dataset.data_dictionary_rows, dataset.file_name)

    return df


# ── Dataset Definitions ──────────────────────────────────────────────────────
# Each definition fully specifies a clean dataset.
# Adding a new dataset = adding a new instance here.

ALL_FACTSHEET_DATASETS = []  # populated after definitions below

TOTAL_POPULATION = ACSDataset(
    table_id="B01003",
    name="total_population",
    title="Total Population",
    description="Total population count for Baltimore City from ACS 5-Year estimates.",
    columns=[
        ColumnDef(
            census_variable="B01003_001E",
            name="total_population",
            description="Total population estimate",
            universe="Total population",
        ),
        ColumnDef(
            census_variable="B01003_001M",
            name="total_population_moe",
            description="Margin of error for total population estimate",
            universe="Total population",
            notes="90% confidence interval. None means MOE was suppressed by Census.",
        ),
    ],
)

MEDIAN_HOUSEHOLD_INCOME = ACSDataset(
    table_id="B19013",
    name="median_household_income",
    title="Median Household Income",
    description=(
        "Median household income in the past 12 months. "
        "Each vintage is inflation-adjusted to that year's dollars."
    ),
    columns=[
        ColumnDef(
            census_variable="B19013_001E",
            name="median_household_income",
            description="Median household income (inflation-adjusted dollars)",
            universe="Households",
            notes="Inflation-adjusted to the ACS vintage year's dollars. Comparing across years requires adjusting for inflation.",
        ),
        ColumnDef(
            census_variable="B19013_001M",
            name="median_household_income_moe",
            description="Margin of error for median household income",
            universe="Households",
        ),
    ],
)

EMPLOYMENT_STATUS = ACSDataset(
    table_id="B23025",
    name="employment_status",
    title="Employment Status",
    description=(
        "Employment status of the civilian population 16 years and over. "
        "Used to compute unemployment rate."
    ),
    start_year=2011,  # B23025 not available in ACS 1-Year before 2011
    columns=[
        ColumnDef(
            census_variable="B23025_001E",
            name="pop_16_and_over",
            description="Total population 16 years and over",
            universe="Population 16 years and over",
        ),
        ColumnDef(
            census_variable="B23025_002E",
            name="in_labor_force",
            description="Population in labor force",
            universe="Population 16 years and over",
        ),
        ColumnDef(
            census_variable="B23025_003E",
            name="civilian_labor_force",
            description="Civilian labor force",
            universe="Population 16 years and over",
        ),
        ColumnDef(
            census_variable="B23025_004E",
            name="employed",
            description="Employed civilian population",
            universe="Civilian labor force",
        ),
        ColumnDef(
            census_variable="B23025_005E",
            name="unemployed",
            description="Unemployed civilian population",
            universe="Civilian labor force",
        ),
        ColumnDef(
            census_variable="B23025_003M",
            name="civilian_labor_force_moe",
            description="Margin of error for civilian labor force",
            universe="Population 16 years and over",
        ),
        ColumnDef(
            census_variable="B23025_005M",
            name="unemployed_moe",
            description="Margin of error for unemployed count",
            universe="Civilian labor force",
        ),
    ],
)

EDUCATION_ATTAINMENT = ACSDataset(
    table_id="B15003",
    name="education_attainment",
    title="Educational Attainment",
    description=(
        "Educational attainment for the population 25 years and over. "
        "Serves two metrics: % with Bachelor's+ and % less than HS diploma."
    ),
    start_year=2008,  # B15003 not available in ACS 1-Year before 2008
    columns=[
        ColumnDef(
            census_variable="B15003_001E",
            name="pop_25_and_over",
            description="Total population 25 years and over",
            universe="Population 25 years and over",
        ),
        # Less than HS diploma: variables 002-016
        ColumnDef(census_variable="B15003_002E", name="no_schooling",
                  description="No schooling completed", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_003E", name="nursery_school",
                  description="Nursery school", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_004E", name="kindergarten",
                  description="Kindergarten", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_005E", name="grade_1",
                  description="1st grade", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_006E", name="grade_2",
                  description="2nd grade", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_007E", name="grade_3",
                  description="3rd grade", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_008E", name="grade_4",
                  description="4th grade", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_009E", name="grade_5",
                  description="5th grade", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_010E", name="grade_6",
                  description="6th grade", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_011E", name="grade_7",
                  description="7th grade", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_012E", name="grade_8",
                  description="8th grade", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_013E", name="grade_9",
                  description="9th grade", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_014E", name="grade_10",
                  description="10th grade", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_015E", name="grade_11",
                  description="11th grade", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_016E", name="grade_12_no_diploma",
                  description="12th grade, no diploma", universe="Population 25 years and over"),
        # HS and above: 017-025
        ColumnDef(census_variable="B15003_017E", name="hs_diploma",
                  description="Regular high school diploma", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_018E", name="ged",
                  description="GED or alternative credential", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_019E", name="some_college_lt_1yr",
                  description="Some college, less than 1 year", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_020E", name="some_college_1yr_plus",
                  description="Some college, 1+ years, no degree", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_021E", name="associates_degree",
                  description="Associate's degree", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_022E", name="bachelors_degree",
                  description="Bachelor's degree", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_023E", name="masters_degree",
                  description="Master's degree", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_024E", name="professional_degree",
                  description="Professional school degree", universe="Population 25 years and over"),
        ColumnDef(census_variable="B15003_025E", name="doctorate_degree",
                  description="Doctorate degree", universe="Population 25 years and over"),
        ColumnDef(
            census_variable="B15003_001M",
            name="pop_25_and_over_moe",
            description="Margin of error for total population 25+",
            universe="Population 25 years and over",
        ),
    ],
)

MORTGAGE_COSTS = ACSDataset(
    table_id="B25091",
    name="mortgage_costs",
    title="Monthly Owner Costs as % of Income (With Mortgage)",
    description=(
        "Selected monthly owner costs as a percentage of household income "
        "for units with a mortgage. Used to compute mortgage cost burden rate."
    ),
    columns=[
        ColumnDef(census_variable="B25091_001E", name="total_with_mortgage",
                  description="Total housing units with a mortgage",
                  universe="Owner-occupied housing units with a mortgage"),
        ColumnDef(census_variable="B25091_002E", name="computed_total",
                  description="Units where cost ratio is computed",
                  universe="Owner-occupied housing units with a mortgage",
                  notes="Excludes units with zero/negative income."),
        ColumnDef(census_variable="B25091_003E", name="less_than_10_pct",
                  description="Less than 10.0% of income",
                  universe="Owner-occupied housing units with a mortgage"),
        ColumnDef(census_variable="B25091_004E", name="pct_10_to_14_9",
                  description="10.0 to 14.9% of income",
                  universe="Owner-occupied housing units with a mortgage"),
        ColumnDef(census_variable="B25091_005E", name="pct_15_to_19_9",
                  description="15.0 to 19.9% of income",
                  universe="Owner-occupied housing units with a mortgage"),
        ColumnDef(census_variable="B25091_006E", name="pct_20_to_24_9",
                  description="20.0 to 24.9% of income",
                  universe="Owner-occupied housing units with a mortgage"),
        ColumnDef(census_variable="B25091_007E", name="pct_25_to_29_9",
                  description="25.0 to 29.9% of income",
                  universe="Owner-occupied housing units with a mortgage"),
        # 30%+ = cost burdened
        ColumnDef(census_variable="B25091_008E", name="pct_30_to_34_9",
                  description="30.0 to 34.9% of income",
                  universe="Owner-occupied housing units with a mortgage"),
        ColumnDef(census_variable="B25091_009E", name="pct_35_to_39_9",
                  description="35.0 to 39.9% of income",
                  universe="Owner-occupied housing units with a mortgage"),
        ColumnDef(census_variable="B25091_010E", name="pct_40_to_49_9",
                  description="40.0 to 49.9% of income",
                  universe="Owner-occupied housing units with a mortgage"),
        ColumnDef(census_variable="B25091_011E", name="pct_50_or_more",
                  description="50.0% or more of income",
                  universe="Owner-occupied housing units with a mortgage"),
        ColumnDef(census_variable="B25091_012E", name="not_computed",
                  description="Not computed (zero or negative income)",
                  universe="Owner-occupied housing units with a mortgage"),
    ],
)

RENT_COSTS = ACSDataset(
    table_id="B25070",
    name="rent_costs",
    title="Gross Rent as % of Household Income",
    description=(
        "Gross rent as a percentage of household income for renter-occupied units. "
        "Used to compute rental cost burden rate."
    ),
    columns=[
        ColumnDef(census_variable="B25070_001E", name="total_renters",
                  description="Total renter-occupied housing units",
                  universe="Renter-occupied housing units"),
        ColumnDef(census_variable="B25070_002E", name="less_than_10_pct",
                  description="Less than 10.0% of income",
                  universe="Renter-occupied housing units"),
        ColumnDef(census_variable="B25070_003E", name="pct_10_to_14_9",
                  description="10.0 to 14.9% of income",
                  universe="Renter-occupied housing units"),
        ColumnDef(census_variable="B25070_004E", name="pct_15_to_19_9",
                  description="15.0 to 19.9% of income",
                  universe="Renter-occupied housing units"),
        ColumnDef(census_variable="B25070_005E", name="pct_20_to_24_9",
                  description="20.0 to 24.9% of income",
                  universe="Renter-occupied housing units"),
        ColumnDef(census_variable="B25070_006E", name="pct_25_to_29_9",
                  description="25.0 to 29.9% of income",
                  universe="Renter-occupied housing units"),
        # 30%+ = rent burdened
        ColumnDef(census_variable="B25070_007E", name="pct_30_to_34_9",
                  description="30.0 to 34.9% of income",
                  universe="Renter-occupied housing units"),
        ColumnDef(census_variable="B25070_008E", name="pct_35_to_39_9",
                  description="35.0 to 39.9% of income",
                  universe="Renter-occupied housing units"),
        ColumnDef(census_variable="B25070_009E", name="pct_40_to_49_9",
                  description="40.0 to 49.9% of income",
                  universe="Renter-occupied housing units"),
        ColumnDef(census_variable="B25070_010E", name="pct_50_or_more",
                  description="50.0% or more of income",
                  universe="Renter-occupied housing units"),
        ColumnDef(census_variable="B25070_011E", name="not_computed",
                  description="Not computed (zero/negative income, no cash rent)",
                  universe="Renter-occupied housing units"),
    ],
)

HOUSEHOLD_SIZE = ACSDataset(
    table_id="B25010",
    name="household_size",
    title="Average Household Size",
    description="Average household size of occupied housing units.",
    columns=[
        ColumnDef(census_variable="B25010_001E", name="avg_household_size",
                  description="Average household size of occupied housing units",
                  universe="Occupied housing units"),
        ColumnDef(census_variable="B25010_001M", name="avg_household_size_moe",
                  description="Margin of error for average household size",
                  universe="Occupied housing units"),
        ColumnDef(census_variable="B25010_002E", name="avg_household_size_owner",
                  description="Average household size of owner-occupied units",
                  universe="Owner-occupied housing units"),
        ColumnDef(census_variable="B25010_003E", name="avg_household_size_renter",
                  description="Average household size of renter-occupied units",
                  universe="Renter-occupied housing units"),
    ],
)

POVERTY_STATUS = ACSDataset(
    table_id="B17001",
    name="poverty_status",
    title="Poverty Status",
    description=(
        "Poverty status in the past 12 months for the population for whom "
        "poverty status is determined. Used to compute the overall poverty rate."
    ),
    columns=[
        ColumnDef(
            census_variable="B17001_001E",
            name="poverty_universe",
            description="Total population for whom poverty status is determined",
            universe="Population for whom poverty status is determined",
        ),
        ColumnDef(
            census_variable="B17001_002E",
            name="below_poverty",
            description="Population with income below the poverty level in the past 12 months",
            universe="Population for whom poverty status is determined",
        ),
        ColumnDef(
            census_variable="B17001_001M",
            name="poverty_universe_moe",
            description="Margin of error for poverty universe",
            universe="Population for whom poverty status is determined",
        ),
        ColumnDef(
            census_variable="B17001_002M",
            name="below_poverty_moe",
            description="Margin of error for population below poverty",
            universe="Population for whom poverty status is determined",
        ),
    ],
)

HOUSING_TENURE = ACSDataset(
    table_id="B25003",
    name="housing_tenure",
    title="Housing Tenure",
    description=(
        "Tenure of occupied housing units — owner-occupied vs. renter-occupied. "
        "Used to compute homeownership rate."
    ),
    columns=[
        ColumnDef(
            census_variable="B25003_001E",
            name="total_occupied_units",
            description="Total occupied housing units",
            universe="Occupied housing units",
        ),
        ColumnDef(
            census_variable="B25003_002E",
            name="owner_occupied",
            description="Owner-occupied housing units",
            universe="Occupied housing units",
        ),
        ColumnDef(
            census_variable="B25003_003E",
            name="renter_occupied",
            description="Renter-occupied housing units",
            universe="Occupied housing units",
        ),
        ColumnDef(
            census_variable="B25003_001M",
            name="total_occupied_units_moe",
            description="Margin of error for total occupied units",
            universe="Occupied housing units",
        ),
    ],
)

HOUSING_OCCUPANCY = ACSDataset(
    table_id="B25002",
    name="housing_occupancy",
    title="Housing Occupancy",
    description=(
        "Occupancy status of all housing units — occupied vs. vacant. "
        "Used to compute the housing vacancy rate."
    ),
    columns=[
        ColumnDef(
            census_variable="B25002_001E",
            name="total_housing_units",
            description="Total housing units",
            universe="Housing units",
        ),
        ColumnDef(
            census_variable="B25002_002E",
            name="occupied_units",
            description="Occupied housing units",
            universe="Housing units",
        ),
        ColumnDef(
            census_variable="B25002_003E",
            name="vacant_units",
            description="Vacant housing units",
            universe="Housing units",
        ),
        ColumnDef(
            census_variable="B25002_001M",
            name="total_housing_units_moe",
            description="Margin of error for total housing units",
            universe="Housing units",
        ),
    ],
)

RACE_ETHNICITY = ACSDataset(
    table_id="B03002",
    name="race_ethnicity",
    title="Race and Hispanic Origin",
    description=(
        "Population by race and Hispanic or Latino origin. "
        "Uses the Hispanic-origin-by-race classification: non-Hispanic categories "
        "are mutually exclusive, and Hispanic/Latino spans all races."
    ),
    columns=[
        ColumnDef(
            census_variable="B03002_001E",
            name="total_population",
            description="Total population",
            universe="Total population",
        ),
        ColumnDef(
            census_variable="B03002_003E",
            name="white_non_hispanic",
            description="White alone, not Hispanic or Latino",
            universe="Total population",
        ),
        ColumnDef(
            census_variable="B03002_004E",
            name="black_non_hispanic",
            description="Black or African American alone, not Hispanic or Latino",
            universe="Total population",
        ),
        ColumnDef(
            census_variable="B03002_005E",
            name="aian_non_hispanic",
            description="American Indian and Alaska Native alone, not Hispanic or Latino",
            universe="Total population",
        ),
        ColumnDef(
            census_variable="B03002_006E",
            name="asian_non_hispanic",
            description="Asian alone, not Hispanic or Latino",
            universe="Total population",
        ),
        ColumnDef(
            census_variable="B03002_007E",
            name="nhpi_non_hispanic",
            description="Native Hawaiian and Other Pacific Islander alone, not Hispanic or Latino",
            universe="Total population",
        ),
        ColumnDef(
            census_variable="B03002_008E",
            name="other_race_non_hispanic",
            description="Some other race alone, not Hispanic or Latino",
            universe="Total population",
        ),
        ColumnDef(
            census_variable="B03002_009E",
            name="two_or_more_non_hispanic",
            description="Two or more races, not Hispanic or Latino",
            universe="Total population",
        ),
        ColumnDef(
            census_variable="B03002_012E",
            name="hispanic_latino",
            description="Hispanic or Latino (of any race)",
            universe="Total population",
        ),
        ColumnDef(
            census_variable="B03002_001M",
            name="total_population_moe",
            description="Margin of error for total population",
            universe="Total population",
        ),
    ],
)

# PEP official annual population estimate
POPULATION_PEP = PEPDataset(
    name="population",
    title="Total Population (Census PEP)",
    description=(
        "Official annual population estimate from the Census Population Estimates "
        "Program. More accurate than ACS for year-to-year tracking of total population."
    ),
    vintage_year=PEP_LATEST_VINTAGE,
)

# BLS LAUS unemployment data
UNEMPLOYMENT_LAUS = BLSDataset(
    series_id="LAUCN245100000000003",  # County-level, not seasonally adjusted
    name="laus_unemployment",
    title="Unemployment Rate (BLS LAUS)",
    description=(
        "Monthly unemployment rate from BLS Local Area Unemployment Statistics. "
        "Annual values are averages of 12 monthly observations."
    ),
    measure="unemployment_rate",
    start_year=2005,
)

ALL_FACTSHEET_DATASETS.extend([
    TOTAL_POPULATION,
    MEDIAN_HOUSEHOLD_INCOME,
    EMPLOYMENT_STATUS,
    EDUCATION_ATTAINMENT,
    MORTGAGE_COSTS,
    RENT_COSTS,
    HOUSEHOLD_SIZE,
    POVERTY_STATUS,
    HOUSING_TENURE,
    HOUSING_OCCUPANCY,
    RACE_ETHNICITY,
])


# ── Open Baltimore Dataset ────────────────────────────────────────────────────


@dataclass
class OpenBaltimoreDataset:
    """Declarative definition for an Open Baltimore (Socrata) dataset.

    Unlike ACS datasets (one API call per year, pre-aggregated),
    Open Baltimore data is incident-level. The pull function queries
    the Socrata API with SoQL aggregation to get annual counts, then
    classifies crime types in pandas.
    """

    dataset_id: str     # 4x4 Socrata ID, e.g. "wsfq-mvij"
    name: str           # Short name for file naming
    title: str          # Human-readable title
    description: str    # What this dataset covers
    start_year: int = 2010

    @property
    def file_name(self) -> str:
        return f"ob_{self.name}"

    @property
    def data_dictionary_rows(self) -> list:
        return [
            {"column": "year", "description": "Calendar year", "notes": ""},
            {"column": "geography", "description": "Geographic area", "notes": "Baltimore City"},
            {"column": "part1_count", "description": "Total Part 1 crime incidents", "notes": "FBI UCR Part 1 classification"},
            {"column": "violent_count", "description": "Violent crime incidents", "notes": "Homicide, rape, robbery, aggravated assault, shooting"},
            {"column": "property_count", "description": "Property crime incidents", "notes": "Burglary, larceny, auto theft, arson"},
            {"column": "homicide_count", "description": "Homicide incidents", "notes": ""},
            {
                "column": "data_quality_flag",
                "description": "Flag for known data quality issues",
                "notes": (
                    f"BPD transitioned Records Management Systems in May {BPD_DATA_QUALITY_ISSUE_YEAR}. "
                    f"Annual totals for {BPD_DATA_QUALITY_ISSUE_YEAR}+ are likely understated."
                ),
            },
        ]


def pull_and_clean_ob_crime_dataset(
    dataset: OpenBaltimoreDataset,
    save: bool = True,
) -> pd.DataFrame:
    """Fetch Open Baltimore crime data, aggregate by year, and classify.

    Process:
    1. Query Socrata with SoQL aggregation (year + description → count)
    2. Save raw aggregated response (Layer 1)
    3. Parse year from ISO datetime string
    4. Classify each description as violent / property
    5. Sum to annual totals: part1, violent, property, homicide
    6. Flag years with known data quality issues

    Args:
        dataset: OpenBaltimoreDataset definition
        save: If True, save clean CSV and data dictionary

    Returns:
        Clean DataFrame: year, geography, part1_count, violent_count,
        property_count, homicide_count, data_quality_flag
    """
    raw = fetch_crime_counts_by_year(
        start_year=dataset.start_year,
        end_year=ACS1_LATEST_YEAR,
    )

    # Layer 1: save raw aggregated response
    save_raw_response(
        raw, "open_baltimore", dataset.dataset_id,
        f"{dataset.start_year}-{ACS1_LATEST_YEAR}", geo="city",
    )

    if not raw:
        raise ValueError(f"No data returned from Open Baltimore dataset {dataset.dataset_id}")

    # Parse and classify each row
    # fetch_crime_counts_by_year returns: {year: int, description: str, count: int}
    records = []
    for row in raw:
        year = row.get("year")
        if year is None:
            continue

        desc = row.get("description", "").strip().upper()
        count = int(row.get("count", 0))
        category = classify_crime(desc)

        records.append({
            "year": year,
            "description": desc,
            "count": count,
            "category": category,
            "is_homicide": desc == "HOMICIDE",
        })

    if not records:
        raise ValueError("Could not parse any crime records from API response")

    detail_df = pd.DataFrame(records)

    # Aggregate to annual totals
    annual = (
        detail_df.groupby("year")
        .apply(lambda g: pd.Series({
            "part1_count":    g.loc[g["category"].notna(), "count"].sum(),
            "violent_count":  g.loc[g["category"] == "violent", "count"].sum(),
            "property_count": g.loc[g["category"] == "property", "count"].sum(),
            "homicide_count": g.loc[g["is_homicide"], "count"].sum(),
        }), include_groups=False)
        .reset_index()
    )

    annual["geography"] = "Baltimore City"
    annual["data_quality_flag"] = annual["year"] >= BPD_DATA_QUALITY_ISSUE_YEAR

    # Reorder columns
    annual = annual[[
        "year", "geography",
        "part1_count", "violent_count", "property_count", "homicide_count",
        "data_quality_flag",
    ]].sort_values("year").reset_index(drop=True)

    if save:
        save_dataset(annual, dataset.file_name)
        save_data_dictionary(dataset.data_dictionary_rows, dataset.file_name)

    return annual


CRIME_PART1 = OpenBaltimoreDataset(
    dataset_id="wsfq-mvij",
    name="crime_part1",
    title="BPD Part 1 Crime",
    description=(
        "Annual Part 1 crime counts from BPD Victim Based Crime Data. "
        "Includes totals for all Part 1, violent, property, and homicide. "
        "⚠️ Data starts 2012 (2010-2011 records are incomplete in source). "
        "⚠️ Data quality issues also exist from May 2021 due to BPD RMS transition."
    ),
    start_year=2012,
)

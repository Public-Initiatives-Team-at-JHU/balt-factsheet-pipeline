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

from src.pipelines.census_acs import fetch_acs_city
from src.utils.config import ACS1_YEARS
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
        years = ACS1_YEARS

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

ALL_FACTSHEET_DATASETS.extend([
    TOTAL_POPULATION,
    MEDIAN_HOUSEHOLD_INCOME,
    EMPLOYMENT_STATUS,
    EDUCATION_ATTAINMENT,
    MORTGAGE_COSTS,
    RENT_COSTS,
    HOUSEHOLD_SIZE,
])

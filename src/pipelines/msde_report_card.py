"""
Maryland State Department of Education (MSDE) Report Card data pipeline.

Fetches school accountability data and details from the Maryland Report Card portal.
Data includes star ratings, indicator scores, and detailed metrics by student group.

Portal: https://reportcard.msde.maryland.gov/
Download page: https://reportcard.msde.maryland.gov/Graphs/#/DataDownloads/datadownload

NOTE: File downloads use numeric IDs, not year-based URLs. The download function
automatically discovers available years by testing ID ranges.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import pandas as pd
import requests

from src.utils.config import RAW_DIR
from src.utils.io import save_data_dictionary, save_dataset


# ── Constants ─────────────────────────────────────────────────────────────────

MSDE_DOWNLOAD_BASE = "https://reportcard.msde.maryland.gov/DataDownloads/FileDownload"
MSDE_REFERER = "https://reportcard.msde.maryland.gov/Graphs/"

# Known file IDs (as of April 2026)
# These are empirically discovered and hard-coded for performance.
# Format: {year: {"accountability_data": id, "accountability_details": id}}
#
# IMPORTANT: Only 4 years exist in this format due to:
#   - 2020-2021: No report cards published (COVID)
#   - 2019 and earlier: Different accountability system (data not available in this format)
#   - 2022-present: Current star rating system
#
# A comprehensive search of file IDs 100-700 confirmed no additional years are available.
KNOWN_FILE_IDS = {
    2022: {"accountability_data": 476, "accountability_details": 477},
    2023: {"accountability_data": 496, "accountability_details": 497},
    2024: {"accountability_data": 536, "accountability_details": 538},
    2025: {"accountability_data": 572, "accountability_details": 574},
}

# Search range for file IDs (used for discovering future years like 2026+)
# Pattern: IDs increment ~20-40 per year, ~2 IDs between data/details for same year
FILE_ID_SEARCH_MIN = 500  # Start from recent range for faster discovery
FILE_ID_SEARCH_MAX = 700  # Expand as needed when new years are published

# Data availability note:
# - 2020-2021: No report cards published (COVID pandemic)
# - 2019 and earlier: Different accountability system; data may exist in legacy formats
# - 2022: First post-COVID report card using current star rating methodology
# - 2022-2025: All years available in current format (verified via comprehensive search)
# - 2026+: Future years will auto-discover when published (typically Nov-Dec release)

# Baltimore City LEA code
BALTIMORE_CITY_LEA = "30"


# ── File ID Discovery ─────────────────────────────────────────────────────────


def discover_file_ids(
    target_years: list[int],
    file_types: list[Literal["accountability_data", "accountability_details"]] = None,
    use_known_ids: bool = True,
) -> dict[int, dict[str, int]]:
    """Discover MSDE download file IDs for target years.

    The MSDE download portal uses numeric file IDs that increment with each release.
    Pattern observed:
    - Accountability Data: one CSV per year (e.g., "2025_Accountability_Schools.csv")
    - Accountability Details: one CSV per year (e.g., "2025_Accountability_Detail.csv")
    - IDs for the same year are typically sequential or near-sequential

    Args:
        target_years: List of years to search for (e.g., [2022, 2023, 2024, 2025])
        file_types: Which file types to search for. Default: both.
        use_known_ids: If True (default), use hard-coded known IDs first

    Returns:
        Dict mapping year → file_type → file_id
        Example: {2025: {"accountability_data": 572, "accountability_details": 574}}

    Raises:
        ValueError: If no files found for any target year
    """
    if file_types is None:
        file_types = ["accountability_data", "accountability_details"]

    print(f"🔍 Searching for MSDE file IDs for years: {target_years}")
    print(f"   File types: {file_types}")

    results = {}

    # First, use known IDs for years we have
    if use_known_ids:
        for year in target_years:
            if year in KNOWN_FILE_IDS:
                results[year] = {}
                for file_type in file_types:
                    if file_type in KNOWN_FILE_IDS[year]:
                        results[year][file_type] = KNOWN_FILE_IDS[year][file_type]
                        print(f"   ✓ Using known ID for {year} {file_type}: {KNOWN_FILE_IDS[year][file_type]}")

    # Identify years that still need discovery
    unknown_years = [
        y for y in target_years
        if y not in results or len(results.get(y, {})) < len(file_types)
    ]

    if not unknown_years:
        return results

    # Search for unknown years
    print(f"   🔎 Searching for unknown years: {unknown_years}")
    print(f"   Search range: ID {FILE_ID_SEARCH_MIN}-{FILE_ID_SEARCH_MAX} (this may take a few minutes)")

    for file_id in range(FILE_ID_SEARCH_MIN, FILE_ID_SEARCH_MAX + 1):
        try:
            # Download and check contents
            response = requests.get(
                f"{MSDE_DOWNLOAD_BASE}/{file_id}",
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": MSDE_REFERER,
                },
                timeout=10,
            )

            if response.status_code != 200:
                continue

            # Check if it's a valid zip
            if not response.content.startswith(b"PK"):
                continue

            # Extract and check filename
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                filenames = zf.namelist()
                if not filenames:
                    continue

                filename = filenames[0]  # Should be single CSV per zip

                # Parse year and type from filename (only for unknown years)
                for year in unknown_years:
                    year_str = str(year)

                    if (
                        "accountability_data" in file_types
                        and f"{year_str}_Accountability_Schools.csv" in filename
                    ):
                        if year not in results:
                            results[year] = {}
                        results[year]["accountability_data"] = file_id
                        print(f"   ✓ Found {year} Accountability Data: ID {file_id}")

                    elif (
                        "accountability_details" in file_types
                        and f"{year_str}_Accountability_Detail.csv" in filename
                    ):
                        if year not in results:
                            results[year] = {}
                        results[year]["accountability_details"] = file_id
                        print(f"   ✓ Found {year} Accountability Details: ID {file_id}")

        except Exception:
            # Skip failed IDs silently
            continue

    if not results:
        raise ValueError(
            f"No MSDE files found for years {target_years}. "
            f"Check if data is available or adjust search range."
        )

    # Report missing years
    missing = [y for y in target_years if y not in results]
    if missing:
        print(f"   ⚠️  No files found for years: {missing}")
        print(
            "   (This is expected for 2020-2021 due to COVID, "
            "or if future years aren't published yet)"
        )

    return results


# ── Download Functions ────────────────────────────────────────────────────────


def download_msde_file(file_id: int, output_path: Path) -> Path:
    """Download a single MSDE file by ID and extract the CSV.

    Args:
        file_id: Numeric file ID from MSDE portal
        output_path: Path where extracted CSV should be saved (including filename)

    Returns:
        Path to the extracted CSV file

    Raises:
        requests.HTTPError: If download fails
        ValueError: If file is not a valid zip or contains multiple files
    """
    response = requests.get(
        f"{MSDE_DOWNLOAD_BASE}/{file_id}",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": MSDE_REFERER,
        },
        timeout=30,
    )
    response.raise_for_status()

    # Validate zip file
    if not response.content.startswith(b"PK"):
        raise ValueError(f"File ID {file_id} did not return a valid zip file")

    # Extract CSV
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        filenames = zf.namelist()
        if len(filenames) != 1:
            raise ValueError(
                f"Expected 1 CSV in zip from ID {file_id}, found {len(filenames)}"
            )

        csv_filename = filenames[0]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(zf.read(csv_filename))

    return output_path


def download_all_years(
    years: list[int] = None,
    file_types: list[Literal["accountability_data", "accountability_details"]] = None,
    force_redownload: bool = False,
) -> dict[int, dict[str, Path]]:
    """Download MSDE accountability data for multiple years.

    Args:
        years: List of years to download. If None, downloads all available years (2022-present).
        file_types: Which file types to download. Default: both.
        force_redownload: If True, re-download even if files already exist.

    Returns:
        Dict mapping year → file_type → Path to downloaded CSV
        Example: {2025: {"accountability_data": Path("..."), ...}}

    Raises:
        ValueError: If no files can be downloaded
    """
    if years is None:
        # Default: all available years (2022 is first year in current format)
        current_year = datetime.now().year
        years = list(range(2022, current_year + 1))

    if file_types is None:
        file_types = ["accountability_data", "accountability_details"]

    print(f"📥 Downloading MSDE Report Card data for {len(years)} years")

    # Discover file IDs
    file_map = discover_file_ids(years, file_types)

    # Download each file
    downloaded = {}
    raw_dir = RAW_DIR / "msde_report_card"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for year, files in file_map.items():
        downloaded[year] = {}

        for file_type, file_id in files.items():
            # Determine output filename
            if file_type == "accountability_data":
                csv_name = f"{year}_Accountability_Schools.csv"
            else:
                csv_name = f"{year}_Accountability_Detail.csv"

            output_path = raw_dir / csv_name

            # Skip if already exists (unless force_redownload)
            if output_path.exists() and not force_redownload:
                print(f"   ✓ {year} {file_type}: already exists (skipping)")
                downloaded[year][file_type] = output_path
                continue

            # Download
            print(f"   📥 Downloading {year} {file_type} (ID {file_id})...")
            try:
                path = download_msde_file(file_id, output_path)
                downloaded[year][file_type] = path
                print(f"      ✓ Saved to {path.name}")
            except Exception as e:
                print(f"      ✗ Failed: {e}")
                continue

    if not downloaded:
        raise ValueError("No files were successfully downloaded")

    print(f"✅ Download complete! {len(downloaded)} years retrieved.")
    return downloaded


# ── Dataset Definitions ───────────────────────────────────────────────────────


@dataclass
class MSDeReportCardDataset:
    """Declarative definition for MSDE Report Card datasets.

    Unlike Census/BLS datasets (which pull from APIs), MSDE data comes from
    pre-aggregated CSV downloads. This class defines metadata and processing
    logic for each dataset type.
    """

    name: str  # Short name for file naming
    title: str  # Human-readable title
    description: str  # What this dataset covers
    file_type: Literal["accountability_data", "accountability_details"]
    start_year: int = 2022  # First year available post-COVID

    @property
    def file_name(self) -> str:
        """Dataset file name without extension. Prefixed with msde_."""
        return f"msde_{self.name}"

    @property
    def data_dictionary_rows(self) -> list:
        """Data dictionary entries for this dataset."""
        if self.file_type == "accountability_data":
            return [
                {
                    "column": "year",
                    "description": "School year (e.g., 2025 = 2024-2025 school year)",
                    "notes": "",
                },
                {
                    "column": "geography",
                    "description": "Geographic level",
                    "notes": "Always 'Baltimore City' for this dataset",
                },
                {
                    "column": "lea",
                    "description": "Local Education Agency (LEA) code",
                    "notes": "30 = Baltimore City",
                },
                {
                    "column": "lea_name",
                    "description": "LEA name",
                    "notes": "",
                },
                {
                    "column": "school",
                    "description": "School code",
                    "notes": "4-digit unique identifier within LEA",
                },
                {
                    "column": "school_name",
                    "description": "School name",
                    "notes": "",
                },
                {
                    "column": "rating",
                    "description": "Star rating (1-5 stars)",
                    "notes": "Maryland School Report Card accountability rating",
                },
                {
                    "column": "total_points_earned_percentage",
                    "description": "Total points earned as percentage of possible points",
                    "notes": "Used to calculate star rating",
                },
            ]
        else:  # accountability_details
            return [
                {
                    "column": "year",
                    "description": "School year (e.g., 2025 = 2024-2025 school year)",
                    "notes": "",
                },
                {
                    "column": "geography",
                    "description": "Geographic level",
                    "notes": "Always 'Baltimore City' for this dataset",
                },
                {
                    "column": "lea",
                    "description": "Local Education Agency (LEA) code",
                    "notes": "30 = Baltimore City",
                },
                {
                    "column": "school",
                    "description": "School code",
                    "notes": "4-digit unique identifier within LEA",
                },
                {
                    "column": "school_name",
                    "description": "School name",
                    "notes": "",
                },
                {
                    "column": "grade_span",
                    "description": "Grade span category (E=Elementary, M=Middle, H=High)",
                    "notes": "",
                },
                {
                    "column": "summary_group_title",
                    "description": "Student group (All Students, race/ethnicity, econ. disadvantaged, etc.)",
                    "notes": "Disaggregated accountability data by subgroup",
                },
                {
                    "column": "indicator_name",
                    "description": "Accountability indicator (Achievement, Progress, Chronic Absenteeism, etc.)",
                    "notes": "",
                },
                {
                    "column": "measure_name",
                    "description": "Specific measure within indicator",
                    "notes": "e.g., Percent Proficient, Growth Percentile",
                },
                {
                    "column": "subject_title",
                    "description": "Subject area (if applicable)",
                    "notes": "Mathematics, ELA, Science, or blank for non-academic indicators",
                },
                {
                    "column": "measure_earned_points",
                    "description": "Points earned for this measure",
                    "notes": "",
                },
                {
                    "column": "measure_value",
                    "description": "Raw value of the measure (%, count, etc.)",
                    "notes": "Format varies by measure type",
                },
            ]


# ── Pull and Clean Functions ──────────────────────────────────────────────────


def pull_and_clean_msde_dataset(
    dataset: MSDeReportCardDataset,
    years: list[int] = None,
    save: bool = True,
    baltimore_city_only: bool = True,
) -> pd.DataFrame:
    """Download and clean MSDE Report Card data.

    Process:
    1. Download raw CSV files (if not already present)
    2. Load and concatenate across years
    3. Standardize column names
    4. Optionally filter to Baltimore City only
    5. Save cleaned dataset

    Args:
        dataset: MSDeReportCardDataset definition
        years: List of years to pull. If None, pulls all available years (2022-present).
        save: If True, save cleaned CSV and data dictionary
        baltimore_city_only: If True, filter to Baltimore City (LEA=30)

    Returns:
        Clean DataFrame with standardized columns
    """
    if years is None:
        # Pull all available years in current format (2022 onwards)
        current_year = datetime.now().year
        years = list(range(dataset.start_year, current_year + 1))

    print(f"📊 Processing {dataset.title}")
    print(f"   Years: {years}")
    print(f"   Baltimore City only: {baltimore_city_only}")

    # Download files
    downloaded = download_all_years(years, file_types=[dataset.file_type])

    # Load and concatenate
    dfs = []
    for year, files in downloaded.items():
        if dataset.file_type not in files:
            continue

        csv_path = files[dataset.file_type]
        print(f"   📄 Loading {csv_path.name}...")

        df = pd.read_csv(csv_path, dtype=str)  # Load as strings initially

        # Standardize column names (lowercase, snake_case)
        df.columns = df.columns.str.lower().str.replace(" ", "_")

        # Add year if not present (should be in file, but defensive)
        if "year" not in df.columns:
            df["year"] = year

        dfs.append(df)

    if not dfs:
        raise ValueError(f"No data loaded for {dataset.name}")

    # Concatenate all years
    combined = pd.concat(dfs, ignore_index=True)

    # Filter to Baltimore City if requested
    if baltimore_city_only:
        if "lea" not in combined.columns:
            raise ValueError("Cannot filter to Baltimore City: 'lea' column missing")

        combined = combined[combined["lea"] == BALTIMORE_CITY_LEA].copy()
        print(f"   ✓ Filtered to Baltimore City: {len(combined):,} rows")

    # Convert year to int
    combined["year"] = pd.to_numeric(combined["year"], errors="coerce").astype("Int64")

    # Convert numeric columns to appropriate types
    if "rating" in combined.columns:
        combined["rating"] = pd.to_numeric(combined["rating"], errors="coerce")
    if "total_points_earned_percentage" in combined.columns:
        combined["total_points_earned_percentage"] = pd.to_numeric(
            combined["total_points_earned_percentage"], errors="coerce"
        )

    # Add geography column for consistency with other datasets
    combined["geography"] = "Baltimore City"

    # Sort by year and school
    sort_cols = ["year"]
    if "school" in combined.columns:
        sort_cols.append("school")
    combined = combined.sort_values(sort_cols).reset_index(drop=True)

    print(f"   ✓ Final dataset: {len(combined):,} rows, {len(combined.columns)} columns")

    if save:
        save_dataset(combined, dataset.file_name)
        save_data_dictionary(dataset.data_dictionary_rows, dataset.file_name)
        print(f"   ✅ Saved to data/datasets/{dataset.file_name}.csv")

    return combined


# ── Dataset Instances ─────────────────────────────────────────────────────────

ACCOUNTABILITY_DATA = MSDeReportCardDataset(
    name="accountability_schools",
    title="School Accountability Summary (Star Ratings)",
    description=(
        "School-level accountability summary with star ratings (1-5), total points, "
        "and percentile ranks. One row per school per year. "
        "⚠️ Data starts 2022 (first post-COVID report card). "
        "No report cards were published for 2019-2020, 2020-2021."
    ),
    file_type="accountability_data",
    start_year=2022,
)

ACCOUNTABILITY_DETAILS = MSDeReportCardDataset(
    name="accountability_details",
    title="School Accountability Details (Indicators by Student Group)",
    description=(
        "Detailed accountability indicators disaggregated by student group. "
        "Includes academic achievement, progress, chronic absenteeism, graduation rate, "
        "and other measures. Multiple rows per school per year (one per indicator × student group). "
        "⚠️ Data starts 2022 (first post-COVID report card). "
        "No report cards were published for 2019-2020, 2020-2021."
    ),
    file_type="accountability_details",
    start_year=2022,
)

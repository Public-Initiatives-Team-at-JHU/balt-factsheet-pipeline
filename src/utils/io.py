from __future__ import annotations

"""
I/O utilities for the three-layer data architecture.

Layer 1 (raw):       save_raw_response  → data/raw/
Layer 2 (datasets):  save_dataset       → data/datasets/
Layer 3 (processed): save_processed     → data/processed/
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.utils.config import DATASETS_DIR, PROCESSED_DIR, RAW_DIR


def save_raw_response(
    data: object,
    source: str,
    table: str,
    year: object,
    geo: str = "city",
) -> Path:
    """Save a raw API response as JSON for audit trail.

    Files are organized into subdirectories by data source:
    - Census (acs5, pep) → data/raw/census/
    - BLS → data/raw/bls/
    - Open Baltimore (open_baltimore, nibrs) → data/raw/open_baltimore/
    - MSDE → data/raw/msde/

    Naming convention: {source}_{table}_{geo}_{year}_{timestamp}.json
    Example: acs5_B01003_city_2023_20260302T143022.json

    The timestamp is UTC so filenames sort chronologically and you never
    overwrite a previous pull of the same table.

    Args:
        data: Raw API response (list-of-lists from Census, dict from BLS, etc.)
        source: Data source identifier (e.g. "acs5", "pep", "bls")
        table: Table or series ID (e.g. "B01003", "LAUS")
        year: Vintage year or year range (e.g. 2023 or "2020-2023")
        geo: Geographic level (e.g. "city", "tracts")

    Returns:
        Path to the saved file.
    """
    # Map source to subdirectory
    source_dirs = {
        "acs5": "census",
        "acs1": "census",
        "pep": "census",
        "bls": "bls",
        "open_baltimore": "open_baltimore",
        "nibrs": "open_baltimore",
        "msde": "msde",
    }
    subdir = source_dirs.get(source, source)  # Use source as fallback if not mapped

    # Create source-specific subdirectory
    source_dir = RAW_DIR / subdir
    source_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    filename = f"{source}_{table}_{geo}_{year}_{timestamp}.json"
    filepath = source_dir / filename

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    return filepath


def save_dataset(df: pd.DataFrame, name: str) -> Path:
    """Save a clean dataset CSV to data/datasets/.

    Args:
        df: Clean DataFrame with human-readable column names
        name: Dataset name, e.g. "acs5_total_population"

    Returns:
        Path to the saved CSV.
    """
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = DATASETS_DIR / f"{name}.csv"
    df.to_csv(filepath, index=False)
    return filepath


def save_data_dictionary(columns: list, name: str) -> Path:
    """Save a data dictionary CSV alongside a dataset.

    The data dictionary explains every column: what Census variable it
    maps to, its universe, and any caveats. Saved with the same base name
    as the dataset plus _data_dictionary suffix.

    Args:
        columns: List of dicts with keys: column, description,
                 census_variable, universe, notes
        name: Dataset name (matches the dataset CSV)

    Returns:
        Path to the saved data dictionary CSV.
    """
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = DATASETS_DIR / f"{name}_data_dictionary.csv"
    pd.DataFrame(columns).to_csv(filepath, index=False)
    return filepath


def save_processed(df: pd.DataFrame, name: str) -> Path:
    """Save a processed output CSV to data/processed/.

    Args:
        df: Dashboard-ready DataFrame
        name: Output name, e.g. "baltimore_factsheet" or "methodology"

    Returns:
        Path to the saved CSV.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    filepath = PROCESSED_DIR / f"{name}.csv"
    df.to_csv(filepath, index=False)
    return filepath

"""
Data validation for clean datasets and computed metrics.

Validates both Layer 2 (clean datasets) and Layer 3 (computed metrics).
Returns structured warnings — the pipeline still completes, but surfaces
anything that looks wrong so a human can investigate.

Each check function returns a list of Warning dicts with:
  - level: "warning" or "error"
  - check: short name of the check
  - message: human-readable description
  - details: optional dict with specifics (indicator, year, value, etc.)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# 2020 ACS 1-Year was not released due to COVID — don't warn about this gap
KNOWN_MISSING_YEARS = {2020}

# Datasets with multiple rows per year-geography by design (monthly, school-level, etc.).
# The year-geography uniqueness check is skipped for these.
MULTI_ROW_DATASETS = {
    "bls_laus_unemployment_monthly",   # one row per month, not per year
    "msde_accountability_schools",     # one row per school
    "msde_accountability_details",     # one row per school × indicator
}


@dataclass
class ValidationResult:
    """Collects validation warnings across all checks."""

    warnings: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.warnings) == 0

    @property
    def error_count(self) -> int:
        return sum(1 for w in self.warnings if w["level"] == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for w in self.warnings if w["level"] == "warning")

    def add(self, level: str, check: str, message: str, **details):
        self.warnings.append({
            "level": level,
            "check": check,
            "message": message,
            "details": details,
        })

    def summary(self) -> str:
        if self.ok:
            return "All validation checks passed."
        lines = [f"Validation: {self.error_count} errors, {self.warning_count} warnings"]
        for w in self.warnings:
            prefix = "ERROR" if w["level"] == "error" else "WARN"
            lines.append(f"  [{prefix}] {w['check']}: {w['message']}")
        return "\n".join(lines)


def validate_dataset(df: pd.DataFrame, dataset_name: str) -> ValidationResult:
    """Validate a clean dataset (Layer 2).

    Checks:
    - No completely empty rows
    - Required columns (year, geography) present
    - No null years
    - No duplicate year-geography combinations
    - Numeric columns don't have unexpected nulls in majority of rows
    """
    result = ValidationResult()

    # Required columns
    for col in ["year", "geography"]:
        if col not in df.columns:
            result.add("error", "missing_column",
                        f"Required column '{col}' missing from {dataset_name}",
                        dataset=dataset_name, column=col)

    if "year" not in df.columns:
        return result  # can't continue without year

    # No empty DataFrame
    if len(df) == 0:
        result.add("error", "empty_dataset",
                    f"{dataset_name} has no rows",
                    dataset=dataset_name)
        return result

    # No null years
    null_years = df["year"].isna().sum()
    if null_years > 0:
        result.add("error", "null_years",
                    f"{dataset_name} has {null_years} rows with null year",
                    dataset=dataset_name, null_count=int(null_years))

    # Duplicate year-geography (skip for school/entity-level datasets)
    if "geography" in df.columns and dataset_name not in MULTI_ROW_DATASETS:
        dupes = df.duplicated(subset=["year", "geography"], keep=False)
        if dupes.any():
            dupe_rows = df[dupes][["year", "geography"]].to_dict("records")
            result.add("error", "duplicate_rows",
                        f"{dataset_name} has {dupes.sum()} duplicate year-geography rows",
                        dataset=dataset_name, duplicates=dupe_rows)

    # Year continuity — check for gaps in the year sequence
    years = sorted(df["year"].dropna().unique())
    if len(years) >= 2:
        expected = list(range(int(years[0]), int(years[-1]) + 1))
        missing = set(expected) - set(int(y) for y in years) - KNOWN_MISSING_YEARS
        if missing:
            result.add("warning", "year_gaps",
                        f"{dataset_name} has gaps in year sequence: missing {sorted(missing)}",
                        dataset=dataset_name, missing_years=sorted(missing))

    # Check for columns that are entirely null (possible API issue)
    for col in df.columns:
        if col in ("year", "geography"):
            continue
        if df[col].isna().all():
            result.add("warning", "all_null_column",
                        f"{dataset_name}.{col} is entirely null",
                        dataset=dataset_name, column=col)

    return result


def validate_factsheet(df: pd.DataFrame) -> ValidationResult:
    """Validate the computed factsheet metrics (Layer 3).

    Checks:
    - Required columns present
    - Percentages in 0-100 range
    - No negative population or income values
    - No null values for indicators that should always have data
    - Year continuity per indicator
    """
    result = ValidationResult()

    # Required columns
    required = ["indicator_id", "indicator_name", "value", "year"]
    for col in required:
        if col not in df.columns:
            result.add("error", "missing_column",
                        f"Required column '{col}' missing from factsheet",
                        column=col)
    if not all(c in df.columns for c in required):
        return result

    # No empty DataFrame
    if len(df) == 0:
        result.add("error", "empty_factsheet", "Factsheet has no rows")
        return result

    # Check each indicator
    for indicator_id, group in df.groupby("indicator_id"):
        _validate_indicator(result, indicator_id, group)

    return result


def _validate_indicator(
    result: ValidationResult,
    indicator_id: str,
    group: pd.DataFrame,
) -> None:
    """Run checks for a single indicator's rows."""

    # Null values
    null_count = group["value"].isna().sum()
    if null_count > 0:
        result.add("warning", "null_values",
                    f"{indicator_id} has {null_count} null values",
                    indicator=indicator_id, null_count=int(null_count))

    values = group["value"].dropna()
    if len(values) == 0:
        return

    # Percentage range check (for indicators with "%" or "rate" in the name)
    name = group["indicator_name"].iloc[0].lower()
    is_percent = any(kw in name for kw in ["%", "rate", "burden"])
    if is_percent:
        out_of_range = values[(values < 0) | (values > 100)]
        if len(out_of_range) > 0:
            result.add("error", "percent_range",
                        f"{indicator_id} has values outside 0-100: {out_of_range.tolist()}",
                        indicator=indicator_id, bad_values=out_of_range.tolist())

    # Negative value check for counts and dollars
    is_count_or_dollars = indicator_id in (
        "total_population", "median_hh_income",
    )
    if is_count_or_dollars:
        negatives = values[values < 0]
        if len(negatives) > 0:
            result.add("error", "negative_values",
                        f"{indicator_id} has negative values: {negatives.tolist()}",
                        indicator=indicator_id, bad_values=negatives.tolist())

    # Year continuity within this indicator
    years = sorted(group["year"].dropna().unique())
    if len(years) >= 2:
        expected = list(range(int(years[0]), int(years[-1]) + 1))
        missing = set(expected) - set(int(y) for y in years) - KNOWN_MISSING_YEARS
        if missing:
            result.add("warning", "indicator_year_gaps",
                        f"{indicator_id} missing years: {sorted(missing)}",
                        indicator=indicator_id, missing_years=sorted(missing))


def validate_all(
    datasets: dict,
    factsheet: pd.DataFrame,
) -> ValidationResult:
    """Run all validation checks on datasets and factsheet.

    Args:
        datasets: Dict mapping dataset file names to DataFrames
        factsheet: Computed factsheet DataFrame

    Returns:
        Combined ValidationResult with all warnings.
    """
    combined = ValidationResult()

    for name, df in datasets.items():
        ds_result = validate_dataset(df, name)
        combined.warnings.extend(ds_result.warnings)

    fs_result = validate_factsheet(factsheet)
    combined.warnings.extend(fs_result.warnings)

    return combined

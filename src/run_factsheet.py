"""
Batch runner for the Baltimore fact sheet pipeline.

Runs the full pipeline end-to-end:
  1. Pulls all clean datasets from Census ACS API (Layer 1 → Layer 2)
  2. Computes all dashboard metrics from datasets (Layer 2 → Layer 3)
  3. Saves everything: datasets, data dictionaries, factsheet CSV, methodology CSV

Usage:
    python3 -m src.run_factsheet
"""
from __future__ import annotations

import sys
import time

from src.pipelines.datasets import (
    ALL_FACTSHEET_DATASETS,
    CRIME_PART1,
    UNEMPLOYMENT_LAUS,
    pull_and_clean_bls_dataset,
    pull_and_clean_dataset,
    pull_and_clean_ob_crime_dataset,
)
from src.pipelines.metrics import (
    ALL_FACTSHEET_METRICS,
    build_methodology_table,
    compute_all_metrics,
    pivot_to_wide,
)
from src.utils.io import save_processed
from src.utils.validation import validate_all

def run() -> dict:
    """Execute the full fact sheet pipeline.

    Returns:
        Summary dict with counts and any warnings from validation.
    """
    start = time.time()
    print("=" * 60)
    print("Baltimore Fact Sheet Pipeline")
    print("=" * 60)

    # ── Layer 2: Pull and clean all datasets ─────────────────────────────────
    print("\n--- Pulling datasets from Census ACS API ---")
    datasets = {}
    for dataset_def in ALL_FACTSHEET_DATASETS:
        print(f"  Pulling {dataset_def.title} ({dataset_def.table_id})...", end=" ")
        df = pull_and_clean_dataset(dataset_def, save=True)
        datasets[dataset_def.file_name] = df
        print(f"{len(df)} rows")

    # Pull BLS LAUS unemployment data
    print("\n--- Pulling BLS LAUS unemployment data ---")
    print(f"  Pulling {UNEMPLOYMENT_LAUS.title} ({UNEMPLOYMENT_LAUS.series_id})...", end=" ")
    try:
        bls_df = pull_and_clean_bls_dataset(UNEMPLOYMENT_LAUS, save=True)
        datasets[UNEMPLOYMENT_LAUS.file_name] = bls_df
        print(f"{len(bls_df)} rows")
    except Exception as e:
        print(f"FAILED: {e}")
        print("  WARNING: Continuing without BLS unemployment data")
        # Pipeline continues with other datasets

    # Pull Open Baltimore crime data
    print("\n--- Pulling Open Baltimore crime data ---")
    print(f"  Pulling {CRIME_PART1.title} ({CRIME_PART1.dataset_id})...", end=" ")
    try:
        crime_df = pull_and_clean_ob_crime_dataset(CRIME_PART1, save=True)
        # Join crime counts with ACS population to produce per-1,000 rates
        pop_df = datasets.get("acs1_total_population")
        if pop_df is not None:
            crime_rates = crime_df.merge(
                pop_df[["year", "total_population"]], on="year", how="left"
            )
            for col in ("part1_count", "violent_count", "property_count", "homicide_count"):
                rate_col = col.replace("_count", "_rate_per_1k")
                crime_rates[rate_col] = (
                    crime_rates[col] / crime_rates["total_population"] * 1000
                ).round(2)
            datasets["ob_crime_rates"] = crime_rates
            print(f"{len(crime_rates)} rows")
        else:
            print("SKIPPED rate computation — ACS population not available")
    except Exception as e:
        print(f"FAILED: {e}")
        print("  WARNING: Continuing without crime data")

    # ── Layer 3: Compute metrics ─────────────────────────────────────────────
    print("\n--- Computing dashboard metrics ---")
    long_df = compute_all_metrics(ALL_FACTSHEET_METRICS, datasets)

    # Primary output: wide format — one row per year, one column per metric
    wide_df = pivot_to_wide(long_df, ALL_FACTSHEET_METRICS)
    save_processed(wide_df, "baltimore_factsheet")
    print(f"  {len(wide_df)} years × {len(wide_df.columns) - 1} metrics → baltimore_factsheet.csv")

    # Secondary output: long format (useful for Power BI and programmatic use)
    save_processed(long_df, "baltimore_factsheet_long")
    print(f"  {len(long_df)} rows → baltimore_factsheet_long.csv")

    # ── Metadata (metric definitions and sources) ────────────────────────────
    metadata = build_methodology_table(ALL_FACTSHEET_METRICS)
    save_processed(metadata, "baltimore_factsheet_metadata")
    print(f"  {len(metadata)} metric definitions → baltimore_factsheet_metadata.csv")

    # ── Validation ───────────────────────────────────────────────────────────
    print("\n--- Validating outputs ---")
    validation = validate_all(datasets, long_df)
    print(f"  {validation.summary()}")

    elapsed = time.time() - start
    print(f"\n--- Done in {elapsed:.1f}s ---")
    print(f"  Datasets: {len(datasets)}")
    print(f"  Metrics:  {len(ALL_FACTSHEET_METRICS)}")
    print(f"  Years (wide):  {len(wide_df)}")
    print(f"  Columns (wide): {len(wide_df.columns)}")

    return {
        "datasets_count": len(datasets),
        "metrics_count": len(ALL_FACTSHEET_METRICS),
        "years": len(wide_df),
        "columns": len(wide_df.columns),
        "elapsed_seconds": round(elapsed, 1),
        "validation_ok": validation.ok,
        "validation_errors": validation.error_count,
        "validation_warnings": validation.warning_count,
    }


if __name__ == "__main__":
    try:
        summary = run()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)

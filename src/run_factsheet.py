"""
Batch runner for the Baltimore fact sheet pipeline.

Runs the full pipeline end-to-end:
  1. Pulls all clean datasets from Census ACS API (Layer 1 → Layer 2)
  2. Computes all dashboard metrics from datasets (Layer 2 → Layer 3)
  3. Saves everything: datasets, data dictionaries, factsheet CSV, methodology CSV

Usage:
    python3 -m src.run_factsheet

New to this code? This is the file that runs everything. You normally don't
need to edit it: to change WHAT the fact sheet shows, edit
src/pipelines/metrics.py (the numbers) or src/pipelines/datasets.py (the
source tables). The outputs Power BI reads land in data/02 processed/.
"""
from __future__ import annotations

import sys
import time

from src.pipelines.datasets import (
    ALL_FACTSHEET_DATASETS,
    CRIME_PART1,
    CRIME_NIBRS_GROUPA,
    ENROLLMENT_CCD,
    QCEW_PRIVATE_EMPLOYMENT,
    UNEMPLOYMENT_LAUS,
    pull_and_clean_bls_dataset,
    pull_and_clean_ccd_dataset,
    pull_and_clean_dataset,
    pull_and_clean_ob_crime_dataset,
    pull_and_clean_nibrs_dataset,
)
from src.pipelines.msde_report_card import (
    ACCOUNTABILITY_DATA,
    ACCOUNTABILITY_DETAILS,
    pull_and_clean_msde_dataset,
)
from src.pipelines.metrics import (
    ALL_FACTSHEET_METRICS,
    aggregate_msde_schools_by_year,
    build_methodology_table,
    compute_all_metrics,
    pivot_to_wide,
)
from src.pipelines.equity_datasets import (
    ALL_EQUITY_DATASETS,
    build_equity_methodology_table,
    compute_equity_metrics,
    pull_equity_dataset,
)
from src.utils.config import PROCESSED_DIR
from src.utils.io import save_processed
from src.utils.provenance import add_provenance, check_output_dir, pipeline_version
from src.utils.validation import validate_all


def _attach_crime_rates(
    crime_df: "pd.DataFrame",
    pop_df: "pd.DataFrame",
    count_cols: tuple,
) -> "pd.DataFrame":
    """Join crime counts to ACS population and add per-1,000 rate columns."""
    import pandas as pd
    rates = crime_df.merge(pop_df[["year", "total_population"]], on="year", how="left")
    for col in count_cols:
        rate_col = col.replace("_count", "_rate_per_1k")
        rates[rate_col] = (rates[col] / rates["total_population"] * 1000).round(2)
    return rates


def run() -> dict:
    """Execute the full fact sheet pipeline.

    Returns:
        Summary dict with counts and any warnings from validation.
    """
    start = time.time()
    print("=" * 60)
    print("Baltimore Fact Sheet Pipeline")
    print("=" * 60)
    check_output_dir(PROCESSED_DIR)
    print(f"Outputs will be written to: {PROCESSED_DIR}")
    print(f"Code version: {pipeline_version()}")

    # ── Layer 2: Pull and clean all datasets ─────────────────────────────────
    print("\n--- Pulling datasets from Census ACS API ---")
    datasets = {}
    for dataset_def in ALL_FACTSHEET_DATASETS:
        print(f"  Pulling {dataset_def.title} ({dataset_def.table_id})...", end=" ")
        df = pull_and_clean_dataset(dataset_def, save=True)
        datasets[dataset_def.file_name] = df
        print(f"{len(df)} rows")

    # Pull BLS data: LAUS unemployment and QCEW private-sector jobs
    print("\n--- Pulling BLS data (LAUS unemployment, QCEW jobs) ---")
    for bls_dataset in (UNEMPLOYMENT_LAUS, QCEW_PRIVATE_EMPLOYMENT):
        print(f"  Pulling {bls_dataset.title} ({bls_dataset.series_id})...", end=" ")
        try:
            bls_df = pull_and_clean_bls_dataset(bls_dataset, save=True)
            datasets[bls_dataset.file_name] = bls_df
            print(f"{len(bls_df)} rows")
        except Exception as e:
            # Pipeline continues with other datasets
            print(f"FAILED: {e}")
            print(f"  WARNING: Continuing without {bls_dataset.title}")

    # Pull Open Baltimore crime data (SRS legacy)
    print("\n--- Pulling Open Baltimore crime data (SRS) ---")
    print(f"  Pulling {CRIME_PART1.title} ({CRIME_PART1.dataset_id})...", end=" ")
    try:
        crime_df = pull_and_clean_ob_crime_dataset(CRIME_PART1, save=True)
        pop_df = datasets.get("acs1_total_population")
        if pop_df is not None:
            crime_rates = _attach_crime_rates(
                crime_df, pop_df,
                ("part1_count", "violent_count", "property_count", "homicide_count"),
            )
            datasets["ob_crime_rates"] = crime_rates
            print(f"{len(crime_rates)} rows")
        else:
            print("SKIPPED rate computation — ACS population not available")
    except Exception as e:
        print(f"FAILED: {e}")
        print("  WARNING: Continuing without SRS crime data")

    # Pull NIBRS crime data (2022-present)
    print("\n--- Pulling Open Baltimore NIBRS crime data ---")
    print(f"  Pulling {CRIME_NIBRS_GROUPA.title}...", end=" ")
    try:
        nibrs_df = pull_and_clean_nibrs_dataset(CRIME_NIBRS_GROUPA, save=True)
        pop_df = datasets.get("acs1_total_population")
        if pop_df is not None:
            nibrs_rates = _attach_crime_rates(
                nibrs_df, pop_df,
                ("groupa_count", "violent_count", "property_count", "homicide_count"),
            )
            datasets["nibrs_crime_rates"] = nibrs_rates
            print(f"{len(nibrs_rates)} rows")
        else:
            print("SKIPPED rate computation — ACS population not available")
    except Exception as e:
        print(f"FAILED: {e}")
        print("  WARNING: Continuing without NIBRS crime data")

    # Pull NCES CCD enrollment data
    print("\n--- Pulling NCES CCD enrollment data ---")
    print(f"  Pulling {ENROLLMENT_CCD.title}...", end=" ")
    try:
        ccd_df = pull_and_clean_ccd_dataset(ENROLLMENT_CCD, save=True)
        datasets[ENROLLMENT_CCD.file_name] = ccd_df
        print(f"{len(ccd_df)} rows")
    except Exception as e:
        print(f"FAILED: {e}")
        print("  WARNING: Continuing without NCES CCD enrollment data")

    # Pull MSDE Report Card data (Baltimore City schools)
    print("\n--- Pulling MSDE Report Card data ---")
    print(f"  Pulling {ACCOUNTABILITY_DATA.title}...", end=" ")
    try:
        msde_schools = pull_and_clean_msde_dataset(
            ACCOUNTABILITY_DATA,
            years=[2022, 2023, 2024, 2025],
            save=True,
            baltimore_city_only=True,
        )
        datasets[ACCOUNTABILITY_DATA.file_name] = msde_schools
        print(f"{len(msde_schools)} rows")

        # Aggregate school-level data to city-level for factsheet metrics
        msde_city_agg = aggregate_msde_schools_by_year(msde_schools)
        datasets["msde_accountability_city_aggregated"] = msde_city_agg
        print(f"  Aggregated to city-level: {len(msde_city_agg)} years")
    except Exception as e:
        print(f"FAILED: {e}")
        print("  WARNING: Continuing without MSDE accountability data")

    print(f"  Pulling {ACCOUNTABILITY_DETAILS.title}...", end=" ")
    try:
        msde_details = pull_and_clean_msde_dataset(
            ACCOUNTABILITY_DETAILS,
            years=[2022, 2023, 2024, 2025],
            save=True,
            baltimore_city_only=True,
        )
        datasets[ACCOUNTABILITY_DETAILS.file_name] = msde_details
        print(f"{len(msde_details)} rows")
    except Exception as e:
        print(f"FAILED: {e}")
        print("  WARNING: Continuing without MSDE accountability details")

    # ── Layer 3: Compute metrics ─────────────────────────────────────────────
    print("\n--- Computing dashboard metrics ---")
    long_df = compute_all_metrics(ALL_FACTSHEET_METRICS, datasets)

    # Primary output: wide format — one row per year, one column per metric
    wide_df = pivot_to_wide(long_df, ALL_FACTSHEET_METRICS)
    save_processed(wide_df, "baltimore_factsheet")
    print(f"  {len(wide_df)} years × {len(wide_df.columns) - 1} metrics → baltimore_factsheet.csv")

    # ── Metadata (metric definitions and sources) ────────────────────────────
    metadata = add_provenance(build_methodology_table(ALL_FACTSHEET_METRICS))
    save_processed(metadata, "baltimore_factsheet_metadata")
    print(f"  {len(metadata)} metric definitions → baltimore_factsheet_metadata.csv")

    # ── Equity breakdowns: race/ethnicity disaggregation ────────────────────
    print("\n--- Pulling equity (race/ethnicity) datasets ---")
    equity_datasets: dict = {}
    for eq_dataset in ALL_EQUITY_DATASETS:
        label = f"{eq_dataset.title} ({eq_dataset.table_id})"
        print(f"  {label}...", end=" ")
        try:
            df = pull_equity_dataset(eq_dataset, save=True)
            equity_datasets[eq_dataset.file_name] = df
            print(f"{len(df)} rows")
        except Exception as e:
            print(f"FAILED: {e}")

    if equity_datasets:
        import pandas as pd
        print("\n--- Computing equity metrics ---")
        equity_df = compute_equity_metrics(equity_datasets)
        n_groups = equity_df["demographic_group"].nunique()
        n_indicators = equity_df["indicator_id"].nunique()
        print(
            f"  {len(equity_df)} rows "
            f"({n_indicators} indicators × {n_groups} groups)"
        )

        # Merge into unified long file: aggregate rows get demographic_group="All",
        # equity rows carry the specific race/ethnicity label.
        combined_long_df = pd.concat([long_df, equity_df], ignore_index=True)
        save_processed(combined_long_df, "baltimore_factsheet_long")
        print(
            f"  {len(combined_long_df)} total rows "
            f"(aggregate + equity) → baltimore_factsheet_long.csv"
        )

        equity_metadata = add_provenance(build_equity_methodology_table())
        save_processed(equity_metadata, "baltimore_factsheet_equity_metadata")
        print(
            f"  {len(equity_metadata)} equity indicator definitions "
            f"→ baltimore_factsheet_equity_metadata.csv"
        )
    else:
        print("  WARNING: No equity datasets available — skipping equity output")
        equity_df = None

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
    if equity_df is not None:
        print(f"  Equity rows: {len(equity_df)}")

    return {
        "datasets_count": len(datasets),
        "metrics_count": len(ALL_FACTSHEET_METRICS),
        "years": len(wide_df),
        "columns": len(wide_df.columns),
        "elapsed_seconds": round(elapsed, 1),
        "validation_ok": validation.ok,
        "validation_errors": validation.error_count,
        "validation_warnings": validation.warning_count,
        "equity_rows": len(equity_df) if equity_df is not None else 0,
    }


if __name__ == "__main__":
    try:
        summary = run()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)

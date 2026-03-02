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

from src.pipelines.datasets import ALL_FACTSHEET_DATASETS, pull_and_clean_dataset
from src.pipelines.metrics import (
    ALL_FACTSHEET_METRICS,
    build_methodology_table,
    compute_all_metrics,
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

    # ── Layer 3: Compute metrics ─────────────────────────────────────────────
    print("\n--- Computing dashboard metrics ---")
    factsheet = compute_all_metrics(ALL_FACTSHEET_METRICS, datasets)
    save_processed(factsheet, "baltimore_factsheet")
    print(f"  {len(factsheet)} metric rows saved to baltimore_factsheet.csv")

    # ── Methodology table ────────────────────────────────────────────────────
    methodology = build_methodology_table(ALL_FACTSHEET_METRICS)
    save_processed(methodology, "methodology")
    print(f"  {len(methodology)} methodology rows saved to methodology.csv")

    # ── Validation ───────────────────────────────────────────────────────────
    print("\n--- Validating outputs ---")
    validation = validate_all(datasets, factsheet)
    print(f"  {validation.summary()}")

    elapsed = time.time() - start
    print(f"\n--- Done in {elapsed:.1f}s ---")
    print(f"  Datasets: {len(datasets)}")
    print(f"  Metrics:  {len(ALL_FACTSHEET_METRICS)}")
    print(f"  Years:    {factsheet['year'].nunique()}")
    print(f"  Total output rows: {len(factsheet)}")

    return {
        "datasets_count": len(datasets),
        "metrics_count": len(ALL_FACTSHEET_METRICS),
        "rows": len(factsheet),
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

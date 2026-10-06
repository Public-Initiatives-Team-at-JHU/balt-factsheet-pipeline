"""Regenerate fact sheet from existing datasets (avoid Census API timeout)."""

import pandas as pd
from pathlib import Path
from src.pipelines.metrics import (
    ALL_FACTSHEET_METRICS,
    build_methodology_table,
    compute_all_metrics,
    pivot_to_wide,
)
from src.utils.io import save_processed

print("Loading existing datasets...")
datasets = {}
dataset_dir = Path("data/datasets")

# Load all CSV files in datasets directory
for csv_file in dataset_dir.glob("*.csv"):
    if "data_dictionary" not in csv_file.name:
        dataset_name = csv_file.stem
        df = pd.read_csv(csv_file)
        datasets[dataset_name] = df
        print(f"  ✓ {dataset_name}: {len(df)} rows")

print(f"\nLoaded {len(datasets)} datasets")

print("\n--- Computing dashboard metrics ---")
long_df = compute_all_metrics(ALL_FACTSHEET_METRICS, datasets)

# Primary output: wide format
wide_df = pivot_to_wide(long_df, ALL_FACTSHEET_METRICS)
save_processed(wide_df, "baltimore_factsheet")
print(f"  {len(wide_df)} years × {len(wide_df.columns) - 1} metrics → baltimore_factsheet.csv")

# Secondary output: long format
save_processed(long_df, "baltimore_factsheet_long")
print(f"  {len(long_df)} rows → baltimore_factsheet_long.csv")

# Metadata
metadata = build_methodology_table(ALL_FACTSHEET_METRICS)
save_processed(metadata, "baltimore_factsheet_metadata")
print(f"  {len(metadata)} metric definitions → baltimore_factsheet_metadata.csv")

print("\n✅ Done! Fact sheet regenerated with corrected crime metrics.")

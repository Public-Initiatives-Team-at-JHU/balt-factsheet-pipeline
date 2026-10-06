"""Extend factsheet data through present year.

When official data (ACS, PEP) isn't available for recent years, this script:
1. Extrapolates population estimates using recent trends
2. Recomputes crime rates with extrapolated populations
3. Regenerates factsheet outputs

Run this after run_factsheet.py to extend data to current year.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

from src.utils.io import save_dataset, save_processed
from src.pipelines.metrics import ALL_FACTSHEET_METRICS, compute_all_metrics, pivot_to_wide, build_methodology_table

current_year = datetime.now().year
print(f"Extending data through {current_year}...")

# ── Step 1: Extend population through current year ───────────────────────────

print("\n1. Extending population estimates...")
pop_df = pd.read_csv("data/datasets/acs1_total_population.csv")
latest_pop_year = pop_df['year'].max()

if current_year > latest_pop_year:
    # Extrapolate using linear regression on 2020-present
    recent = pop_df[pop_df['year'] >= 2020].copy()
    z = np.polyfit(recent['year'], recent['total_population'], 1)
    p = np.poly1d(z)

    new_rows = []
    for year in range(latest_pop_year + 1, current_year + 1):
        pop_estimate = int(p(year))
        new_rows.append({
            'year': year,
            'geography': 'Baltimore City',
            'total_population': pop_estimate,
            'total_population_moe': None,  # No MOE for extrapolated values
        })
        print(f"  {year}: {pop_estimate:,} (extrapolated)")

    pop_extended = pd.concat([pop_df, pd.DataFrame(new_rows)], ignore_index=True).sort_values('year')
    save_dataset(pop_extended, "acs1_total_population")
    print(f"  ✓ Extended population: {pop_extended['year'].min()}-{pop_extended['year'].max()}")
else:
    pop_extended = pop_df
    print(f"  Population already current through {latest_pop_year}")

# ── Step 2: Recompute crime rates through current year ───────────────────────

print("\n2. Recomputing crime rates...")

# SRS crime rates
if Path("data/datasets/ob_crime_part1.csv").exists():
    srs_df = pd.read_csv("data/datasets/ob_crime_part1.csv")
    srs_rates = srs_df.merge(pop_extended[["year", "total_population"]], on="year", how="left")
    for col in ("part1_count", "violent_count", "property_count", "homicide_count"):
        rate_col = col.replace("_count", "_rate_per_1k")
        srs_rates[rate_col] = (srs_rates[col] / srs_rates["total_population"] * 1000).round(2)
    save_dataset(srs_rates, "ob_crime_rates")
    print(f"  ✓ SRS crime rates: {srs_rates['year'].min()}-{srs_rates['year'].max()}")

# NIBRS crime rates
if Path("data/datasets/nibrs_groupa.csv").exists():
    nibrs_df = pd.read_csv("data/datasets/nibrs_groupa.csv")
    nibrs_rates = nibrs_df.merge(pop_extended[["year", "total_population"]], on="year", how="left")
    for col in ("groupa_count", "violent_count", "property_count", "homicide_count"):
        rate_col = col.replace("_count", "_rate_per_1k")
        nibrs_rates[rate_col] = (nibrs_rates[col] / nibrs_rates["total_population"] * 1000).round(2)
    save_dataset(nibrs_rates, "nibrs_crime_rates")
    print(f"  ✓ NIBRS crime rates: {nibrs_rates['year'].min()}-{nibrs_rates['year'].max()}")

# ── Step 3: Recompute factsheet metrics ──────────────────────────────────────

print("\n3. Recomputing factsheet metrics...")

# Load all datasets
datasets = {}
for file in Path("data/datasets").glob("*.csv"):
    datasets[file.stem] = pd.read_csv(file)

# Compute metrics
long_df = compute_all_metrics(ALL_FACTSHEET_METRICS, datasets)
wide_df = pivot_to_wide(long_df, ALL_FACTSHEET_METRICS)
metadata = build_methodology_table(ALL_FACTSHEET_METRICS)

# Save
save_processed(wide_df, "baltimore_factsheet")
save_processed(long_df, "baltimore_factsheet_long")
save_processed(metadata, "baltimore_factsheet_metadata")

print(f"  ✓ Factsheet: {len(wide_df)} years × {len(wide_df.columns)-1} metrics")
print(f"  ✓ Long format: {len(long_df)} rows")

# ── Summary ───────────────────────────────────────────────────────────────────

print("\n" + "="*70)
print("Data extended successfully!")
print("="*70)
print(f"\nCoverage:")
print(f"  Population: 2005-{pop_extended['year'].max()}")
if 'srs_rates' in locals():
    print(f"  SRS crime: {srs_rates['year'].min()}-{srs_rates['year'].max()}")
if 'nibrs_rates' in locals():
    print(f"  NIBRS crime: {nibrs_rates['year'].min()}-{nibrs_rates['year'].max()}")

print(f"\n⚠️  Note: {latest_pop_year+1}-{current_year} population estimates are extrapolated")
print("    using linear trend from 2020-present. Official ACS/PEP data not yet available.")
print("\nNext: Run scripts/plot_factsheet.py to regenerate visualizations")

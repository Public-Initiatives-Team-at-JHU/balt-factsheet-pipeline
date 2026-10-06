"""Quick script to recompute crime metrics with corrected classifications."""

import pandas as pd
from src.pipelines.datasets import CRIME_PART1, pull_and_clean_ob_crime_dataset
from src.utils.io import save_dataset

# Pull fresh crime data with corrected classifications
print("Pulling BPD Part 1 crime data with corrected classifications...")
crime_df = pull_and_clean_ob_crime_dataset(CRIME_PART1, save=True)
print(f"✓ {len(crime_df)} rows")

# Load existing population data
print("Loading existing ACS population data...")
pop_df = pd.read_csv("data/datasets/acs1_total_population.csv")
print(f"✓ {len(pop_df)} rows")

# Join and compute rates
print("Computing crime rates...")
crime_rates = crime_df.merge(
    pop_df[["year", "total_population"]], on="year", how="left"
)

for col in ("part1_count", "violent_count", "property_count", "homicide_count"):
    rate_col = col.replace("_count", "_rate_per_1k")
    crime_rates[rate_col] = (
        crime_rates[col] / crime_rates["total_population"] * 1000
    ).round(2)

# Save
save_dataset(crime_rates, "ob_crime_rates")
print(f"✓ Saved ob_crime_rates.csv")

# Show sample
print("\nSample (2023):")
sample = crime_rates[crime_rates["year"] == 2023].iloc[0]
print(f"  Violent count: {sample['violent_count']}")
print(f"  Property count: {sample['property_count']}")
print(f"  Part 1 count: {sample['part1_count']}")
print(f"  Violent rate: {sample['violent_rate_per_1k']} per 1,000")
print("\nDone!")

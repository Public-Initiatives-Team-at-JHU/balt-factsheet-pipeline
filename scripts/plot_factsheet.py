"""Quick time series plots for Baltimore fact sheet metrics."""

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from pathlib import Path

# Read the data
data = pd.read_csv("data/processed/baltimore_factsheet.csv")

# Create output folder
output_dir = Path("data/visualizations")
output_dir.mkdir(exist_ok=True)

# Get unique metrics
metrics = data["indicator_id"].unique()

# Plot each metric
for metric_id in metrics:
    metric_data = data[data["indicator_id"] == metric_id].sort_values("year")

    plt.figure(figsize=(10, 6))
    plt.plot(metric_data["year"], metric_data["value"], marker='o', linewidth=2)
    plt.title(metric_data["indicator_name"].iloc[0], fontsize=14, fontweight='bold')
    plt.xlabel("Year")
    plt.ylabel(metric_data["indicator_name"].iloc[0])
    plt.grid(True, alpha=0.3)

    # Force x-axis to show whole years only (no decimals like "2021.5")
    plt.gca().xaxis.set_major_locator(MaxNLocator(integer=True))

    plt.tight_layout()

    # Save
    plt.savefig(output_dir / f"{metric_id}.png", dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ {metric_id}.png")

print(f"\nDone! Saved {len(metrics)} charts to {output_dir}")

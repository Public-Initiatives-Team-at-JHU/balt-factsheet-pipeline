"""Quick time series plots for Baltimore fact sheet metrics.

Square format with minimal annotation for clean dashboard embedding.
"""

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from pathlib import Path

# Read the long-format data
data = pd.read_csv("data/processed/baltimore_factsheet_long.csv")

# Create output folder
output_dir = Path("data/visualizations")
output_dir.mkdir(exist_ok=True)

# Get unique metrics
metrics = data["indicator_id"].unique()

# Plot each metric
for metric_id in metrics:
    metric_data = data[data["indicator_id"] == metric_id].sort_values("year")

    # Square format (8x8) with minimal annotation
    plt.figure(figsize=(8, 8))
    plt.plot(
        metric_data["year"],
        metric_data["value"],
        marker='o',
        linewidth=3,
        markersize=8,
        color='#1f77b4',
    )

    # Minimal title only (no axis labels)
    plt.title(
        metric_data["indicator_name"].iloc[0],
        fontsize=16,
        fontweight='bold',
        pad=15,
    )

    # Light grid
    plt.grid(True, alpha=0.2, linewidth=0.5)

    # Force x-axis to show whole years only
    plt.gca().xaxis.set_major_locator(MaxNLocator(integer=True))

    # Larger tick labels for readability
    plt.xticks(fontsize=12)
    plt.yticks(fontsize=12)

    plt.tight_layout()

    # Save
    plt.savefig(output_dir / f"{metric_id}.png", dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ {metric_id}.png")

print(f"\nDone! Saved {len(metrics)} charts to {output_dir}")

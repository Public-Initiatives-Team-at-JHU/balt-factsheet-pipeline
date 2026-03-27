"""Quick time series plots for Baltimore fact sheet metrics.

Square format with minimal annotation for clean dashboard embedding.
Handles dual reporting for crime metrics (SRS + NIBRS overlap 2022-2024).
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

# Define crime metric pairs (SRS → NIBRS mapping)
CRIME_METRIC_PAIRS = {
    "part1_crime_rate_per_1k": "groupa_crime_rate_per_1k_nibrs",
    "violent_crime_rate_per_1k": "violent_crime_rate_per_1k_nibrs",
    "property_crime_rate_per_1k": "property_crime_rate_per_1k_nibrs",
    "homicide_count": "homicide_count_nibrs",
}

# Get unique metrics
metrics = data["indicator_id"].unique()

# Plot each metric
for metric_id in metrics:
    metric_data = data[data["indicator_id"] == metric_id].sort_values("year")

    # Check if this is a crime metric with a NIBRS counterpart
    has_nibrs_pair = metric_id in CRIME_METRIC_PAIRS
    nibrs_metric_id = CRIME_METRIC_PAIRS.get(metric_id)

    # Square format (8x8) with minimal annotation
    plt.figure(figsize=(8, 8))

    if has_nibrs_pair:
        # Dual reporting mode: plot both SRS and NIBRS
        nibrs_data = data[data["indicator_id"] == nibrs_metric_id].sort_values("year")

        # Plot SRS (legacy) — solid blue line
        plt.plot(
            metric_data["year"],
            metric_data["value"],
            marker='o',
            linewidth=3,
            markersize=8,
            color='#1f77b4',
            label='SRS (legacy)',
        )

        # Plot NIBRS (current) — dashed orange line
        plt.plot(
            nibrs_data["year"],
            nibrs_data["value"],
            marker='s',
            linewidth=3,
            markersize=8,
            color='#ff7f0e',
            linestyle='--',
            label='NIBRS (current)',
        )

        # Add legend
        plt.legend(loc='best', fontsize=11, framealpha=0.9)

        # Add methodology change annotation
        plt.axvline(x=2024.5, color='gray', linestyle=':', linewidth=1.5, alpha=0.5)
        plt.text(
            2024.5, plt.ylim()[1] * 0.95,
            'Methodology\nChange',
            fontsize=9,
            ha='center',
            va='top',
            color='gray',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='gray', alpha=0.8)
        )

        # Title (strip [NIBRS] suffix from name if present)
        title = metric_data["indicator_name"].iloc[0].replace(" [NIBRS]", "")
        source_note = f"SRS: {metric_data['source'].iloc[0]} | NIBRS: {nibrs_data['source'].iloc[0]}"

    else:
        # Single metric mode: standard plot
        plt.plot(
            metric_data["year"],
            metric_data["value"],
            marker='o',
            linewidth=3,
            markersize=8,
            color='#1f77b4',
        )
        title = metric_data["indicator_name"].iloc[0]
        source_note = f"Source: {metric_data['source'].iloc[0]}"

    # Title
    plt.title(
        title,
        fontsize=16,
        fontweight='bold',
        pad=20,
        loc='center',
    )

    # Add source annotation just below title
    plt.text(
        0.5,
        0.98,
        source_note,
        transform=plt.gca().transAxes,
        fontsize=9,
        ha='center',
        va='top',
        style='italic',
        color='#555555',
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
print(f"  - {len([m for m in metrics if m in CRIME_METRIC_PAIRS])} charts with dual SRS/NIBRS reporting")
print(f"  - {len([m for m in metrics if m not in CRIME_METRIC_PAIRS and not m.endswith('_nibrs')])} standard charts")

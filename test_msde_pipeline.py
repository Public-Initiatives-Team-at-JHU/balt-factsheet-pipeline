#!/usr/bin/env python3
"""Test script for MSDE Report Card pipeline."""

from src.pipelines.msde_report_card import (
    ACCOUNTABILITY_DATA,
    ACCOUNTABILITY_DETAILS,
    pull_and_clean_msde_dataset,
)

if __name__ == "__main__":
    print("=" * 80)
    print("Testing MSDE Report Card Pipeline")
    print("=" * 80)

    # Test 1: Download and process accountability data (schools summary)
    print("\n📊 Test 1: Accountability Data (School Summary with Star Ratings)")
    print("-" * 80)
    df_schools = pull_and_clean_msde_dataset(
        ACCOUNTABILITY_DATA,
        years=[2022, 2023, 2024, 2025],  # Explicitly request 4 available years
        save=True,
        baltimore_city_only=True,
    )
    print(f"\n✅ Loaded {len(df_schools):,} schools")
    print(f"   Columns: {list(df_schools.columns)}")
    print(f"   Years: {sorted(df_schools['year'].unique())}")
    print(f"\n   Sample data:")
    print(df_schools.head(3))

    # Test 2: Download and process accountability details
    print("\n" + "=" * 80)
    print("📊 Test 2: Accountability Details (Indicators by Student Group)")
    print("-" * 80)
    df_details = pull_and_clean_msde_dataset(
        ACCOUNTABILITY_DETAILS,
        years=[2022, 2023, 2024, 2025],
        save=True,
        baltimore_city_only=True,
    )
    print(f"\n✅ Loaded {len(df_details):,} detail records")
    print(f"   Columns: {list(df_details.columns)}")
    print(f"   Years: {sorted(df_details['year'].unique())}")
    print(f"   Unique indicators: {df_details['indicator_name'].nunique()}")
    print(f"\n   Sample data:")
    print(df_details.head(3))

    print("\n" + "=" * 80)
    print("✅ All tests passed!")
    print("=" * 80)

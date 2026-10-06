#!/usr/bin/env python3
"""
Validate computed metrics in the Baltimore fact sheet against raw dataset files.
Cross-checks calculations to ensure accuracy.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).resolve().parent / "data"
DATASETS_DIR = DATA_DIR / "datasets"
PROCESSED_DIR = DATA_DIR / "processed"

def load_data():
    """Load fact sheet and raw dataset files."""
    # Fact sheet
    factsheet_long = pd.read_csv(PROCESSED_DIR / "baltimore_factsheet_long.csv")
    metadata = pd.read_csv(PROCESSED_DIR / "baltimore_factsheet_metadata.csv")

    # Raw datasets
    poverty = pd.read_csv(DATASETS_DIR / "acs1_poverty_status.csv")
    education = pd.read_csv(DATASETS_DIR / "acs1_education_attainment.csv")
    unemployment = pd.read_csv(DATASETS_DIR / "bls_laus_unemployment_monthly.csv")
    housing_tenure = pd.read_csv(DATASETS_DIR / "acs1_housing_tenure.csv")

    return factsheet_long, metadata, {
        'poverty': poverty,
        'education': education,
        'unemployment': unemployment,
        'housing_tenure': housing_tenure
    }

def verify_poverty_rate(factsheet, raw_data, years):
    """Verify poverty rate calculation: below_poverty / poverty_universe × 100"""
    results = []
    poverty_df = raw_data['poverty']

    for year in years:
        # Get fact sheet value
        fs_row = factsheet[(factsheet['indicator_id'] == 'poverty_rate') & (factsheet['year'] == year)]
        if fs_row.empty:
            results.append({
                'metric': 'poverty_rate',
                'year': year,
                'status': '⚠️ MISSING',
                'factsheet_value': None,
                'calculated_value': None,
                'match': False,
                'note': 'No data in fact sheet for this year'
            })
            continue

        fs_value = fs_row['value'].values[0]

        # Get raw data
        raw_row = poverty_df[poverty_df['year'] == year]
        if raw_row.empty:
            results.append({
                'metric': 'poverty_rate',
                'year': year,
                'status': '⚠️ MISSING',
                'factsheet_value': fs_value,
                'calculated_value': None,
                'match': False,
                'note': 'No raw data for this year'
            })
            continue

        # Calculate
        below_poverty = raw_row['below_poverty'].values[0]
        poverty_universe = raw_row['poverty_universe'].values[0]
        calculated = (below_poverty / poverty_universe) * 100

        # Compare (allow for floating point precision and rounding)
        # Use rtol=1e-3 (0.1%) to account for rounding differences
        match = np.isclose(fs_value, calculated, rtol=1e-3)

        results.append({
            'metric': 'poverty_rate',
            'year': year,
            'status': '✅ VERIFIED' if match else '❌ ERROR',
            'factsheet_value': round(fs_value, 2),
            'calculated_value': round(calculated, 2),
            'match': match,
            'note': '' if match else f'Difference: {abs(fs_value - calculated):.4f}%'
        })

    return results

def verify_bachelors_degree_plus(factsheet, raw_data, years):
    """Verify Bachelor's+ calculation: (bach + masters + prof + doc) / pop_25+ × 100"""
    results = []
    education_df = raw_data['education']

    for year in years:
        # Get fact sheet value
        fs_row = factsheet[(factsheet['indicator_id'] == 'bachelors_degree_plus') & (factsheet['year'] == year)]
        if fs_row.empty:
            results.append({
                'metric': 'bachelors_degree_plus',
                'year': year,
                'status': '⚠️ MISSING',
                'factsheet_value': None,
                'calculated_value': None,
                'match': False,
                'note': 'No data in fact sheet for this year'
            })
            continue

        fs_value = fs_row['value'].values[0]

        # Get raw data
        raw_row = education_df[education_df['year'] == year]
        if raw_row.empty:
            results.append({
                'metric': 'bachelors_degree_plus',
                'year': year,
                'status': '⚠️ MISSING',
                'factsheet_value': fs_value,
                'calculated_value': None,
                'match': False,
                'note': 'No raw data for this year'
            })
            continue

        # Calculate
        bachelors = raw_row['bachelors_degree'].values[0]
        masters = raw_row['masters_degree'].values[0]
        professional = raw_row['professional_degree'].values[0]
        doctorate = raw_row['doctorate_degree'].values[0]
        pop_25_plus = raw_row['pop_25_and_over'].values[0]

        calculated = ((bachelors + masters + professional + doctorate) / pop_25_plus) * 100

        # Compare (allow for floating point precision and rounding)
        match = np.isclose(fs_value, calculated, rtol=1e-3)

        results.append({
            'metric': 'bachelors_degree_plus',
            'year': year,
            'status': '✅ VERIFIED' if match else '❌ ERROR',
            'factsheet_value': round(fs_value, 2),
            'calculated_value': round(calculated, 2),
            'match': match,
            'note': '' if match else f'Difference: {abs(fs_value - calculated):.4f}%'
        })

    return results

def verify_less_than_hs_diploma(factsheet, raw_data, years):
    """Verify <HS diploma calculation: sum(no_schooling through grade_12_no_diploma) / pop_25+ × 100"""
    results = []
    education_df = raw_data['education']

    for year in years:
        # Get fact sheet value
        fs_row = factsheet[(factsheet['indicator_id'] == 'less_than_hs_diploma') & (factsheet['year'] == year)]
        if fs_row.empty:
            results.append({
                'metric': 'less_than_hs_diploma',
                'year': year,
                'status': '⚠️ MISSING',
                'factsheet_value': None,
                'calculated_value': None,
                'match': False,
                'note': 'No data in fact sheet for this year'
            })
            continue

        fs_value = fs_row['value'].values[0]

        # Get raw data
        raw_row = education_df[education_df['year'] == year]
        if raw_row.empty:
            results.append({
                'metric': 'less_than_hs_diploma',
                'year': year,
                'status': '⚠️ MISSING',
                'factsheet_value': fs_value,
                'calculated_value': None,
                'match': False,
                'note': 'No raw data for this year'
            })
            continue

        # Calculate - sum all education levels below HS diploma
        less_than_hs_cols = [
            'no_schooling', 'nursery_school', 'kindergarten',
            'grade_1', 'grade_2', 'grade_3', 'grade_4', 'grade_5',
            'grade_6', 'grade_7', 'grade_8', 'grade_9', 'grade_10',
            'grade_11', 'grade_12_no_diploma'
        ]

        less_than_hs = sum(raw_row[col].values[0] for col in less_than_hs_cols)
        pop_25_plus = raw_row['pop_25_and_over'].values[0]

        calculated = (less_than_hs / pop_25_plus) * 100

        # Compare (allow for floating point precision and rounding)
        match = np.isclose(fs_value, calculated, rtol=1e-3)

        results.append({
            'metric': 'less_than_hs_diploma',
            'year': year,
            'status': '✅ VERIFIED' if match else '❌ ERROR',
            'factsheet_value': round(fs_value, 2),
            'calculated_value': round(calculated, 2),
            'match': match,
            'note': '' if match else f'Difference: {abs(fs_value - calculated):.4f}%'
        })

    return results

def verify_unemployment_rate(factsheet, raw_data, years):
    """Verify BLS unemployment rate: annual average of monthly values"""
    results = []
    unemployment_df = raw_data['unemployment']

    for year in years:
        # Get fact sheet value
        fs_row = factsheet[(factsheet['indicator_id'] == 'unemployment_rate_bls') & (factsheet['year'] == year)]
        if fs_row.empty:
            results.append({
                'metric': 'unemployment_rate_bls',
                'year': year,
                'status': '⚠️ MISSING',
                'factsheet_value': None,
                'calculated_value': None,
                'match': False,
                'note': 'No data in fact sheet for this year'
            })
            continue

        fs_value = fs_row['value'].values[0]

        # Get monthly data
        monthly = unemployment_df[unemployment_df['year'] == year]
        if monthly.empty:
            results.append({
                'metric': 'unemployment_rate_bls',
                'year': year,
                'status': '⚠️ MISSING',
                'factsheet_value': fs_value,
                'calculated_value': None,
                'match': False,
                'note': 'No raw data for this year'
            })
            continue

        # Calculate annual average
        # Note: The raw data already has annual_unemployment_rate computed
        # But let's verify it from monthly values
        monthly_rates = monthly['monthly_unemployment_rate'].dropna()
        calculated = monthly_rates.mean()

        # Compare (allow for floating point precision and rounding)
        match = np.isclose(fs_value, calculated, rtol=1e-3)

        results.append({
            'metric': 'unemployment_rate_bls',
            'year': year,
            'status': '✅ VERIFIED' if match else '❌ ERROR',
            'factsheet_value': round(fs_value, 2),
            'calculated_value': round(calculated, 2),
            'match': match,
            'note': '' if match else f'Difference: {abs(fs_value - calculated):.4f}% | Months: {len(monthly_rates)}'
        })

    return results

def verify_homeownership_rate(factsheet, raw_data, years):
    """Verify homeownership rate: owner_occupied / total_occupied_units × 100"""
    results = []
    housing_df = raw_data['housing_tenure']

    for year in years:
        # Get fact sheet value
        fs_row = factsheet[(factsheet['indicator_id'] == 'homeownership_rate') & (factsheet['year'] == year)]
        if fs_row.empty:
            results.append({
                'metric': 'homeownership_rate',
                'year': year,
                'status': '⚠️ MISSING',
                'factsheet_value': None,
                'calculated_value': None,
                'match': False,
                'note': 'No data in fact sheet for this year'
            })
            continue

        fs_value = fs_row['value'].values[0]

        # Get raw data
        raw_row = housing_df[housing_df['year'] == year]
        if raw_row.empty:
            results.append({
                'metric': 'homeownership_rate',
                'year': year,
                'status': '⚠️ MISSING',
                'factsheet_value': fs_value,
                'calculated_value': None,
                'match': False,
                'note': 'No raw data for this year'
            })
            continue

        # Calculate
        owner_occupied = raw_row['owner_occupied'].values[0]
        total_occupied = raw_row['total_occupied_units'].values[0]
        calculated = (owner_occupied / total_occupied) * 100

        # Compare (allow for floating point precision and rounding)
        match = np.isclose(fs_value, calculated, rtol=1e-3)

        results.append({
            'metric': 'homeownership_rate',
            'year': year,
            'status': '✅ VERIFIED' if match else '❌ ERROR',
            'factsheet_value': round(fs_value, 2),
            'calculated_value': round(calculated, 2),
            'match': match,
            'note': '' if match else f'Difference: {abs(fs_value - calculated):.4f}%'
        })

    return results

def check_data_completeness(factsheet):
    """Check for missing data across all metrics and years."""
    # Get unique metrics and year range
    metrics = factsheet['indicator_id'].unique()
    years = sorted(factsheet['year'].unique())

    completeness = []
    for metric in metrics:
        metric_data = factsheet[factsheet['indicator_id'] == metric]
        years_present = set(metric_data['year'].values)
        years_missing = set(years) - years_present

        completeness.append({
            'metric': metric,
            'years_present': len(years_present),
            'years_missing': len(years_missing),
            'missing_years': sorted(list(years_missing)) if years_missing else None,
            'coverage': f"{len(years_present)}/{len(years)}"
        })

    return pd.DataFrame(completeness)

def check_value_anomalies(factsheet):
    """Check for suspicious values (sudden jumps, out-of-range values)."""
    anomalies = []

    for metric in factsheet['indicator_id'].unique():
        metric_data = factsheet[factsheet['indicator_id'] == metric].sort_values('year')
        values = metric_data['value'].values
        years = metric_data['year'].values

        # Skip if insufficient data
        if len(values) < 2:
            continue

        # Check for year-over-year changes > 20%
        for i in range(1, len(values)):
            if pd.isna(values[i]) or pd.isna(values[i-1]):
                continue

            pct_change = abs((values[i] - values[i-1]) / values[i-1]) * 100

            # Flag changes > 20% for percentage metrics, or > 50% for counts
            threshold = 50 if 'count' in metric else 20

            if pct_change > threshold:
                anomalies.append({
                    'metric': metric,
                    'year_from': years[i-1],
                    'year_to': years[i],
                    'value_from': round(values[i-1], 2),
                    'value_to': round(values[i], 2),
                    'pct_change': round(pct_change, 2),
                    'note': 'Large year-over-year change'
                })

        # Check for out-of-range values
        # Percentages should be 0-100
        if 'pct_' in metric or 'rate' in metric and 'per_1k' not in metric:
            out_of_range = metric_data[(metric_data['value'] < 0) | (metric_data['value'] > 100)]
            for _, row in out_of_range.iterrows():
                anomalies.append({
                    'metric': metric,
                    'year_from': row['year'],
                    'year_to': row['year'],
                    'value_from': round(row['value'], 2),
                    'value_to': round(row['value'], 2),
                    'pct_change': None,
                    'note': 'Percentage out of range (0-100)'
                })

    return pd.DataFrame(anomalies) if anomalies else pd.DataFrame()

def main():
    print("=" * 80)
    print("BALTIMORE FACT SHEET VALIDATION REPORT")
    print("=" * 80)
    print()

    # Load data
    print("Loading data...")
    factsheet_long, metadata, raw_data = load_data()
    print(f"✓ Fact sheet: {len(factsheet_long)} rows")
    print(f"✓ Metadata: {len(metadata)} indicators")
    print()

    # Test years: focus on recent years
    test_years = [2021, 2022, 2023]

    all_results = []

    # Verify poverty rate
    print("Verifying Poverty Rate...")
    all_results.extend(verify_poverty_rate(factsheet_long, raw_data, test_years))

    # Verify Bachelor's degree+
    print("Verifying Bachelor's Degree or Higher...")
    all_results.extend(verify_bachelors_degree_plus(factsheet_long, raw_data, test_years))

    # Verify <HS diploma
    print("Verifying Less Than High School Diploma...")
    all_results.extend(verify_less_than_hs_diploma(factsheet_long, raw_data, test_years))

    # Verify unemployment
    print("Verifying Unemployment Rate...")
    all_results.extend(verify_unemployment_rate(factsheet_long, raw_data, test_years))

    # Verify homeownership
    print("Verifying Homeownership Rate...")
    all_results.extend(verify_homeownership_rate(factsheet_long, raw_data, test_years))

    print()
    print("=" * 80)
    print("VERIFICATION RESULTS")
    print("=" * 80)
    print()

    results_df = pd.DataFrame(all_results)

    # Display results
    for _, row in results_df.iterrows():
        print(f"{row['status']} {row['metric']} ({row['year']})")
        print(f"   Fact sheet value: {row['factsheet_value']}")
        print(f"   Calculated value: {row['calculated_value']}")
        if row['note']:
            print(f"   Note: {row['note']}")
        print()

    # Summary statistics
    print("=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print()

    verified = results_df[results_df['status'] == '✅ VERIFIED']
    errors = results_df[results_df['status'] == '❌ ERROR']
    missing = results_df[results_df['status'] == '⚠️ MISSING']

    print(f"✅ VERIFIED: {len(verified)}/{len(results_df)}")
    print(f"❌ ERRORS: {len(errors)}/{len(results_df)}")
    print(f"⚠️ MISSING: {len(missing)}/{len(results_df)}")
    print()

    # Data completeness check
    print("=" * 80)
    print("DATA COMPLETENESS BY METRIC")
    print("=" * 80)
    print()

    completeness = check_data_completeness(factsheet_long)
    print(completeness.to_string(index=False))
    print()

    # Anomaly detection
    print("=" * 80)
    print("ANOMALY DETECTION - MISSING DATA")
    print("=" * 80)
    print()

    # Check for unexpected missing years (2020 is expected for ACS, 2024-2025 expected for all)
    has_missing = False
    for _, row in completeness.iterrows():
        if row['missing_years']:
            missing_years = row['missing_years']
            # Filter out expected gaps: 2020 for ACS, 2024-2025 for all (data not yet available)
            expected_missing = {2020, 2024, 2025}
            unexpected = [y for y in missing_years if y not in expected_missing]
            if unexpected:
                print(f"⚠️ {row['metric']}: Missing data for years {unexpected}")
                has_missing = True

    if not has_missing:
        print("✓ No unexpected missing data")

    print()

    # Value anomalies
    print("=" * 80)
    print("ANOMALY DETECTION - VALUE CHANGES")
    print("=" * 80)
    print()

    anomalies = check_value_anomalies(factsheet_long)
    if not anomalies.empty:
        print("⚠️ Found suspicious year-over-year changes:")
        print()
        for _, row in anomalies.iterrows():
            print(f"⚠️ {row['metric']} ({row['year_from']} → {row['year_to']})")
            print(f"   Value: {row['value_from']} → {row['value_to']} ({row['pct_change']:+.1f}% change)")
            print(f"   Note: {row['note']}")
            print()
    else:
        print("✓ No suspicious value changes detected")

    print()
    print("=" * 80)
    print("END OF REPORT")
    print("=" * 80)

if __name__ == "__main__":
    main()

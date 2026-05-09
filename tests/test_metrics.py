"""Tests for src/pipelines/metrics.py — metric computation layer."""

import pandas as pd
import pytest

from src.pipelines.metrics import (
    ALL_FACTSHEET_METRICS,
    K12_ENROLLMENT_METRIC,
    TOTAL_POPULATION_METRIC,
    Metric,
    build_methodology_table,
    compute_all_metrics,
)
from src.utils.config import DASHBOARD_COLUMNS, METHODOLOGY_COLUMNS


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def pop_dataset():
    """Clean dataset DataFrame mimicking acs1_total_population.csv."""
    return pd.DataFrame({
        "year": [2020, 2021, 2022, 2023],
        "geography": ["Baltimore City"] * 4,
        "total_population": [602274, 592211, 584548, 577193],
        "total_population_moe": [None, None, None, None],
    })


@pytest.fixture
def division_metric():
    """A metric that divides two columns — for testing computed metrics."""
    return Metric(
        id="test_rate",
        name="Test Rate",
        description="Test percentage metric",
        compute=lambda row: row["numerator"] / row["denominator"] * 100,
        source_dataset="test_dataset",
        source_table="TEST",
        formula_description="numerator / denominator × 100",
        source_name="Test Source",
        source_url="https://example.com",
        unit="percent",
        update_frequency="annual",
    )


@pytest.fixture
def division_dataset():
    return pd.DataFrame({
        "year": [2023],
        "geography": ["Baltimore City"],
        "numerator": [50],
        "denominator": [200],
    })


# ── compute_all_metrics tests ────────────────────────────────────────────────


class TestComputeAllMetrics:

    def test_output_has_dashboard_columns(self, pop_dataset):
        result = compute_all_metrics(
            [TOTAL_POPULATION_METRIC],
            {"acs1_total_population": pop_dataset},
        )
        assert list(result.columns) == DASHBOARD_COLUMNS

    def test_one_row_per_year(self, pop_dataset):
        result = compute_all_metrics(
            [TOTAL_POPULATION_METRIC],
            {"acs1_total_population": pop_dataset},
        )
        assert len(result) == 4

    def test_indicator_id_populated(self, pop_dataset):
        result = compute_all_metrics(
            [TOTAL_POPULATION_METRIC],
            {"acs1_total_population": pop_dataset},
        )
        assert all(result["indicator_id"] == "total_population")

    def test_values_match_source_data(self, pop_dataset):
        result = compute_all_metrics(
            [TOTAL_POPULATION_METRIC],
            {"acs1_total_population": pop_dataset},
        )
        assert list(result["value"]) == [602274, 592211, 584548, 577193]

    def test_period_format_1year(self, pop_dataset):
        """1-year estimates produce a single year as the period."""
        result = compute_all_metrics(
            [TOTAL_POPULATION_METRIC],
            {"acs1_total_population": pop_dataset},
        )
        assert result.iloc[0]["period"] == "2020"
        assert result.iloc[3]["period"] == "2023"

    def test_period_format_5year(self, pop_dataset):
        """5-year estimates (future tract-level) produce a year range."""
        metric = Metric(
            id="test", name="Test", description="Test",
            compute=lambda row: row["total_population"],
            source_dataset="acs1_total_population",
            source_table="B01003",
            formula_description="test",
            source_name="Test", source_url="", unit="count",
            update_frequency="annual",
            period_format="5-year",
        )
        result = compute_all_metrics(
            [metric], {"acs1_total_population": pop_dataset},
        )
        assert result.iloc[0]["period"] == "2016-2020"

    def test_missing_dataset_skips_metric(self):
        result = compute_all_metrics(
            [TOTAL_POPULATION_METRIC],
            {},  # no datasets provided
        )
        assert len(result) == 0

    def test_computed_metric_division(self, division_metric, division_dataset):
        result = compute_all_metrics(
            [division_metric],
            {"test_dataset": division_dataset},
        )
        assert result.iloc[0]["value"] == 25.0  # 50/200 * 100

    def test_value_rounded_to_2_decimals(self):
        metric = Metric(
            id="test", name="Test", description="Test",
            compute=lambda row: 1 / 3 * 100,  # 33.33333...
            source_dataset="test_ds",
            source_table="TEST",
            formula_description="test",
            source_name="Test", source_url="", unit="percent",
            update_frequency="annual",
        )
        df = pd.DataFrame({
            "year": [2023], "geography": ["Baltimore City"], "x": [1],
        })
        result = compute_all_metrics([metric], {"test_ds": df})
        assert result.iloc[0]["value"] == 33.33

    def test_none_value_not_rounded(self):
        metric = Metric(
            id="test", name="Test", description="Test",
            compute=lambda row: None,
            source_dataset="test_ds",
            source_table="TEST",
            formula_description="test",
            source_name="Test", source_url="", unit="count",
            update_frequency="annual",
        )
        df = pd.DataFrame({
            "year": [2023], "geography": ["Baltimore City"], "x": [1],
        })
        result = compute_all_metrics([metric], {"test_ds": df})
        assert result.iloc[0]["value"] is None

    def test_multiple_metrics_same_dataset(self, pop_dataset):
        metric_a = Metric(
            id="pop_a", name="Pop A", description="A",
            compute=lambda row: row["total_population"],
            source_dataset="acs1_total_population",
            source_table="B01003",
            formula_description="direct",
            source_name="ACS", source_url="", unit="count",
            update_frequency="annual",
        )
        metric_b = Metric(
            id="pop_b", name="Pop B", description="B",
            compute=lambda row: row["total_population"] / 1000,
            source_dataset="acs1_total_population",
            source_table="B01003",
            formula_description="pop / 1000",
            source_name="ACS", source_url="", unit="count",
            update_frequency="annual",
        )
        result = compute_all_metrics(
            [metric_a, metric_b],
            {"acs1_total_population": pop_dataset},
        )
        # 4 years × 2 metrics = 8 rows
        assert len(result) == 8
        assert set(result["indicator_id"]) == {"pop_a", "pop_b"}


# ── build_methodology_table tests ────────────────────────────────────────────


class TestBuildMethodologyTable:

    def test_output_has_methodology_columns(self):
        result = build_methodology_table([TOTAL_POPULATION_METRIC])
        assert list(result.columns) == METHODOLOGY_COLUMNS

    def test_one_row_per_metric(self):
        result = build_methodology_table(ALL_FACTSHEET_METRICS)
        assert len(result) == len(ALL_FACTSHEET_METRICS)

    def test_indicator_id_populated(self):
        result = build_methodology_table([TOTAL_POPULATION_METRIC])
        assert result.iloc[0]["indicator_id"] == "total_population"

    def test_formula_populated(self):
        result = build_methodology_table([TOTAL_POPULATION_METRIC])
        assert "B01003_001E" in result.iloc[0]["formula"]

    def test_last_verified_is_today(self):
        from datetime import date
        result = build_methodology_table([TOTAL_POPULATION_METRIC])
        assert result.iloc[0]["last_verified"] == date.today().isoformat()

    def test_empty_metrics_list(self):
        result = build_methodology_table([])
        assert len(result) == 0
        assert list(result.columns) == METHODOLOGY_COLUMNS


# ── TOTAL_POPULATION_METRIC definition tests ─────────────────────────────────


class TestTotalPopulationMetricDefinition:

    def test_id(self):
        assert TOTAL_POPULATION_METRIC.id == "total_population"

    def test_source_dataset_matches_dataset_file_name(self):
        from src.pipelines.datasets import TOTAL_POPULATION
        assert TOTAL_POPULATION_METRIC.source_dataset == TOTAL_POPULATION.file_name

    def test_unit_is_count(self):
        assert TOTAL_POPULATION_METRIC.unit == "count"


# ── K12_ENROLLMENT_METRIC definition tests ───────────────────────────────────


class TestK12EnrollmentMetric:
    def test_computes_enrollment(self):
        row = pd.Series({"year": 2023, "geography": "Baltimore City", "k12_enrollment": 75100})
        result = K12_ENROLLMENT_METRIC.compute(row)
        assert result == 75100.0

    def test_handles_none(self):
        row = pd.Series({"year": 2023, "geography": "Baltimore City", "k12_enrollment": None})
        result = K12_ENROLLMENT_METRIC.compute(row)
        assert result is None

    def test_handles_nan(self):
        import numpy as np
        row = pd.Series({"year": 2023, "geography": "Baltimore City", "k12_enrollment": np.nan})
        result = K12_ENROLLMENT_METRIC.compute(row)
        assert result is None

    def test_in_all_factsheet_metrics(self):
        ids = [m.id for m in ALL_FACTSHEET_METRICS]
        assert "k12_enrollment_bcpss" in ids

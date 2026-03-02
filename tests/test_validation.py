"""Tests for src/utils/validation.py."""
from __future__ import annotations

import pandas as pd
import pytest

from src.utils.validation import (
    ValidationResult,
    validate_all,
    validate_dataset,
    validate_factsheet,
)


# ── ValidationResult tests ───────────────────────────────────────────────────

class TestValidationResult:

    def test_empty_result_is_ok(self):
        r = ValidationResult()
        assert r.ok is True
        assert r.error_count == 0
        assert r.warning_count == 0

    def test_add_warning(self):
        r = ValidationResult()
        r.add("warning", "test_check", "something odd", indicator="foo")
        assert r.ok is False
        assert r.warning_count == 1
        assert r.error_count == 0
        assert r.warnings[0]["details"]["indicator"] == "foo"

    def test_add_error(self):
        r = ValidationResult()
        r.add("error", "test_check", "something broke")
        assert r.error_count == 1
        assert r.warning_count == 0

    def test_summary_ok(self):
        r = ValidationResult()
        assert "passed" in r.summary().lower()

    def test_summary_with_issues(self):
        r = ValidationResult()
        r.add("error", "bad", "bad thing")
        r.add("warning", "odd", "odd thing")
        summary = r.summary()
        assert "1 errors" in summary
        assert "1 warnings" in summary
        assert "bad" in summary


# ── validate_dataset tests ───────────────────────────────────────────────────

class TestValidateDataset:

    def _make_df(self, **overrides):
        """Build a minimal valid dataset DataFrame."""
        data = {
            "year": [2020, 2021, 2022, 2023],
            "geography": ["Baltimore City"] * 4,
            "value": [100, 200, 300, 400],
        }
        data.update(overrides)
        return pd.DataFrame(data)

    def test_valid_dataset_passes(self):
        df = self._make_df()
        result = validate_dataset(df, "test")
        assert result.ok

    def test_missing_year_column(self):
        df = pd.DataFrame({"geography": ["Baltimore City"], "value": [100]})
        result = validate_dataset(df, "test")
        assert result.error_count >= 1
        assert any(w["check"] == "missing_column" for w in result.warnings)

    def test_missing_geography_column(self):
        df = pd.DataFrame({"year": [2023], "value": [100]})
        result = validate_dataset(df, "test")
        assert any(
            w["check"] == "missing_column" and w["details"]["column"] == "geography"
            for w in result.warnings
        )

    def test_empty_dataset(self):
        df = pd.DataFrame(columns=["year", "geography", "value"])
        result = validate_dataset(df, "test")
        assert any(w["check"] == "empty_dataset" for w in result.warnings)

    def test_null_years(self):
        df = self._make_df(year=[2020, None, 2022, 2023])
        result = validate_dataset(df, "test")
        assert any(w["check"] == "null_years" for w in result.warnings)

    def test_duplicate_year_geography(self):
        df = pd.DataFrame({
            "year": [2023, 2023],
            "geography": ["Baltimore City", "Baltimore City"],
            "value": [100, 200],
        })
        result = validate_dataset(df, "test")
        assert any(w["check"] == "duplicate_rows" for w in result.warnings)

    def test_year_gaps(self):
        df = self._make_df(year=[2020, 2022, 2023, 2023])
        # Note: 2023 duplicate will also trigger, but we're checking year_gaps
        result = validate_dataset(df, "test")
        assert any(w["check"] == "year_gaps" for w in result.warnings)

    def test_all_null_column(self):
        df = self._make_df(value=[None, None, None, None])
        result = validate_dataset(df, "test")
        assert any(w["check"] == "all_null_column" for w in result.warnings)

    def test_no_gap_warning_for_contiguous_years(self):
        df = self._make_df()
        result = validate_dataset(df, "test")
        assert not any(w["check"] == "year_gaps" for w in result.warnings)


# ── validate_factsheet tests ─────────────────────────────────────────────────

class TestValidateFactsheet:

    def _make_factsheet(self, **overrides):
        """Build a minimal valid factsheet DataFrame."""
        data = {
            "indicator_id": ["total_population"] * 4,
            "indicator_name": ["Total Population"] * 4,
            "value": [600000, 590000, 580000, 577000],
            "year": [2020, 2021, 2022, 2023],
        }
        data.update(overrides)
        return pd.DataFrame(data)

    def test_valid_factsheet_passes(self):
        df = self._make_factsheet()
        result = validate_factsheet(df)
        assert result.ok

    def test_missing_required_column(self):
        df = pd.DataFrame({"indicator_id": ["x"], "value": [1]})
        result = validate_factsheet(df)
        assert result.error_count >= 1

    def test_empty_factsheet(self):
        df = pd.DataFrame(columns=["indicator_id", "indicator_name", "value", "year"])
        result = validate_factsheet(df)
        assert any(w["check"] == "empty_factsheet" for w in result.warnings)

    def test_null_values_warning(self):
        df = self._make_factsheet(value=[600000, None, 580000, 577000])
        result = validate_factsheet(df)
        assert any(w["check"] == "null_values" for w in result.warnings)

    def test_percent_out_of_range(self):
        df = self._make_factsheet(
            indicator_id=["unemployment_rate_acs"] * 4,
            indicator_name=["Unemployment Rate"] * 4,
            value=[5.0, 110.0, 6.0, 7.0],
        )
        result = validate_factsheet(df)
        assert any(w["check"] == "percent_range" for w in result.warnings)

    def test_negative_percent(self):
        df = self._make_factsheet(
            indicator_id=["rent_cost_burden_30pct"] * 4,
            indicator_name=["Rent Cost Burden (30%+ of Income)"] * 4,
            value=[-5.0, 50.0, 51.0, 52.0],
        )
        result = validate_factsheet(df)
        assert any(w["check"] == "percent_range" for w in result.warnings)

    def test_negative_population(self):
        df = self._make_factsheet(value=[-100, 590000, 580000, 577000])
        result = validate_factsheet(df)
        assert any(w["check"] == "negative_values" for w in result.warnings)

    def test_negative_income(self):
        df = self._make_factsheet(
            indicator_id=["median_hh_income"] * 4,
            indicator_name=["Median Household Income"] * 4,
            value=[-5000, 54000, 58000, 59000],
        )
        result = validate_factsheet(df)
        assert any(w["check"] == "negative_values" for w in result.warnings)

    def test_year_gaps_in_indicator(self):
        df = self._make_factsheet(year=[2020, 2022, 2023, 2023])
        result = validate_factsheet(df)
        assert any(w["check"] == "indicator_year_gaps" for w in result.warnings)

    def test_valid_percent_in_range(self):
        df = self._make_factsheet(
            indicator_id=["unemployment_rate_acs"] * 4,
            indicator_name=["Unemployment Rate"] * 4,
            value=[6.5, 7.0, 6.8, 6.2],
        )
        result = validate_factsheet(df)
        assert not any(w["check"] == "percent_range" for w in result.warnings)

    def test_burden_keyword_triggers_percent_check(self):
        """'burden' in indicator name should trigger percentage range checks."""
        df = self._make_factsheet(
            indicator_id=["mortgage_cost_burden_30pct"] * 4,
            indicator_name=["Mortgage Cost Burden (30%+ of Income)"] * 4,
            value=[30.0, 31.0, 150.0, 29.0],
        )
        result = validate_factsheet(df)
        assert any(w["check"] == "percent_range" for w in result.warnings)


# ── validate_all integration test ────────────────────────────────────────────

class TestValidateAll:

    def test_combines_dataset_and_factsheet_results(self):
        ds = pd.DataFrame({
            "year": [2023, 2023],
            "geography": ["Baltimore City", "Baltimore City"],
            "value": [100, 200],
        })
        fs = pd.DataFrame({
            "indicator_id": ["total_population"],
            "indicator_name": ["Total Population"],
            "value": [-100],
            "year": [2023],
        })
        result = validate_all({"test_dataset": ds}, fs)
        checks = [w["check"] for w in result.warnings]
        assert "duplicate_rows" in checks      # from dataset
        assert "negative_values" in checks     # from factsheet

    def test_all_clean_data_passes(self):
        ds = pd.DataFrame({
            "year": [2020, 2021, 2022, 2023],
            "geography": ["Baltimore City"] * 4,
            "value": [100, 200, 300, 400],
        })
        fs = pd.DataFrame({
            "indicator_id": ["total_population"] * 4,
            "indicator_name": ["Total Population"] * 4,
            "value": [600000, 590000, 580000, 577000],
            "year": [2020, 2021, 2022, 2023],
        })
        result = validate_all({"test_dataset": ds}, fs)
        assert result.ok

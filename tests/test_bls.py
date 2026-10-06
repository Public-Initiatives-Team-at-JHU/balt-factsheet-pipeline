"""Tests for the BLS dataset layer (LAUS unemployment, QCEW private-sector jobs).

The BLS API is mocked — no network calls. The key behavior under test: an
annual figure is only published once a year is complete (December reported),
so a partial year like Jan–Feb is never presented as an annual average.
"""

from unittest.mock import patch

import pandas as pd
import pytest

from src.pipelines.datasets import (
    QCEW_PRIVATE_EMPLOYMENT,
    UNEMPLOYMENT_LAUS,
    pull_and_clean_bls_dataset,
)
from src.pipelines.metrics import PRIVATE_JOBS_QCEW_METRIC


def _bls_response(points: list) -> dict:
    """Build a BLS API response from (year, period, value) tuples."""
    return {
        "status": "REQUEST_SUCCEEDED",
        "Results": {"series": [{"seriesID": "X", "data": [
            {"year": str(y), "period": p, "value": v} for y, p, v in points
        ]}]},
    }


def _full_year(year: int, value: str) -> list:
    return [(year, f"M{m:02d}", value) for m in range(1, 13)]


@pytest.fixture
def pull():
    """Run pull_and_clean_bls_dataset against a mocked API response."""
    def _pull(dataset, points):
        with patch("src.pipelines.datasets.fetch_bls_laus", return_value=_bls_response(points)), \
             patch("src.pipelines.datasets.save_raw_response") as save_raw:
            df = pull_and_clean_bls_dataset(dataset, save=False)
        return df, save_raw
    return _pull


class TestAnnualAverages:

    def test_full_year_is_mean_of_months(self, pull):
        points = [(2024, f"M{m:02d}", str(m)) for m in range(1, 13)]
        df, _ = pull(UNEMPLOYMENT_LAUS, points)
        assert df["annual_unemployment_rate"].tolist() == [6.5]
        assert df["months_reported"].tolist() == [12]

    def test_year_without_december_is_excluded(self, pull):
        points = _full_year(2025, "5.0") + [(2026, "M01", "6.4"), (2026, "M02", "6.2")]
        df, _ = pull(UNEMPLOYMENT_LAUS, points)
        assert df["year"].tolist() == [2025]

    def test_missing_month_is_skipped_and_counted(self, pull):
        # Oct 2025 was not published (federal shutdown); BLS returns "-"
        points = [(2025, f"M{m:02d}", "-" if m == 10 else "4.0") for m in range(1, 13)]
        df, _ = pull(UNEMPLOYMENT_LAUS, points)
        assert df["annual_unemployment_rate"].tolist() == [4.0]
        assert df["months_reported"].tolist() == [11]

    def test_bls_annual_average_rows_are_ignored(self, pull):
        points = _full_year(2024, "3.0") + [(2024, "M13", "99.0")]
        df, _ = pull(UNEMPLOYMENT_LAUS, points)
        assert df["annual_unemployment_rate"].tolist() == [3.0]


class TestQCEW:

    def test_series_is_private_ownership_all_industries(self):
        # ENU + area 24510 + datatype 1 (employment) + size 0 + ownership 5 (private) + industry 10 (all)
        assert QCEW_PRIVATE_EMPLOYMENT.series_id == "ENU2451010510"

    def test_raw_response_labeled_by_program(self, pull):
        _, save_raw = pull(QCEW_PRIVATE_EMPLOYMENT, _full_year(2025, "269150"))
        assert save_raw.call_args.args[2] == "QCEW"

    def test_data_dictionary_does_not_label_jobs_as_percent(self):
        descriptions = [r["description"] for r in QCEW_PRIVATE_EMPLOYMENT.data_dictionary_rows]
        assert not any("(%)" in d for d in descriptions)

    def test_metric_rounds_to_whole_jobs(self):
        row = pd.Series({"annual_private_employment": 269149.6667})
        assert PRIVATE_JOBS_QCEW_METRIC.compute(row) == 269150

    def test_metric_reads_qcew_dataset(self):
        assert PRIVATE_JOBS_QCEW_METRIC.source_dataset == QCEW_PRIVATE_EMPLOYMENT.file_name

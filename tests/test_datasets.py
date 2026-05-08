"""Tests for src/pipelines/datasets.py — clean dataset layer."""

from unittest.mock import patch

import pandas as pd
import pytest

from src.pipelines.datasets import (
    CENSUS_SUPPRESSED_MOE,
    TOTAL_POPULATION,
    ACSDataset,
    ColumnDef,
    _to_numeric,
    pull_and_clean_dataset,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

# Realistic Census API response for B01003 (Total Population)
MOCK_B01003_RESPONSE = [
    ["B01003_001E", "B01003_001M", "state", "county"],
    ["577193", "-555555555", "24", "510"],
]

# Response with a real MOE value (not suppressed)
MOCK_WITH_MOE_RESPONSE = [
    ["B01003_001E", "B01003_001M", "state", "county"],
    ["577193", "1234", "24", "510"],
]


@pytest.fixture
def simple_dataset():
    """A minimal ACSDataset for testing."""
    return ACSDataset(
        table_id="B01003",
        name="total_population",
        title="Total Population",
        description="Test dataset",
        columns=[
            ColumnDef(
                census_variable="B01003_001E",
                name="total_population",
                description="Total pop",
                universe="Total population",
            ),
            ColumnDef(
                census_variable="B01003_001M",
                name="total_population_moe",
                description="MOE",
                universe="Total population",
                notes="Test note",
            ),
        ],
    )


# ── ACSDataset dataclass tests ───────────────────────────────────────────────


class TestACSDataset:

    def test_file_name_prefix(self, simple_dataset):
        assert simple_dataset.file_name == "acs1_total_population"

    def test_variables_extracts_census_codes(self, simple_dataset):
        assert simple_dataset.variables == ["B01003_001E", "B01003_001M"]

    def test_rename_map(self, simple_dataset):
        expected = {
            "B01003_001E": "total_population",
            "B01003_001M": "total_population_moe",
        }
        assert simple_dataset.rename_map == expected

    def test_data_dictionary_includes_year_and_geography(self, simple_dataset):
        rows = simple_dataset.data_dictionary_rows
        columns = [r["column"] for r in rows]
        assert "year" in columns
        assert "geography" in columns

    def test_data_dictionary_includes_all_columns(self, simple_dataset):
        rows = simple_dataset.data_dictionary_rows
        columns = [r["column"] for r in rows]
        # 2 Census columns + year + geography = 4
        assert len(columns) == 4
        assert "total_population" in columns
        assert "total_population_moe" in columns

    def test_data_dictionary_preserves_notes(self, simple_dataset):
        rows = simple_dataset.data_dictionary_rows
        moe_row = [r for r in rows if r["column"] == "total_population_moe"][0]
        assert moe_row["notes"] == "Test note"

    def test_empty_columns(self):
        ds = ACSDataset(
            table_id="TEST", name="test", title="Test", description="Test"
        )
        assert ds.variables == []
        assert ds.rename_map == {}
        # Still has year + geography
        assert len(ds.data_dictionary_rows) == 2


# ── _to_numeric tests ────────────────────────────────────────────────────────


class TestToNumeric:

    def test_integer_string(self):
        assert _to_numeric("577193") == 577193

    def test_float_string(self):
        assert _to_numeric("2.45") == 2.45

    def test_negative_integer(self):
        assert _to_numeric("-555555555") == -555555555

    def test_none_returns_none(self):
        assert _to_numeric(None) is None

    def test_empty_string_returns_none(self):
        assert _to_numeric("") is None

    def test_non_numeric_string_returns_none(self):
        assert _to_numeric("Baltimore City") is None

    def test_zero(self):
        assert _to_numeric("0") == 0

    def test_integer_preferred_over_float(self):
        """Integers should stay as int, not become 577193.0."""
        result = _to_numeric("577193")
        assert isinstance(result, int)


# ── pull_and_clean_dataset tests ─────────────────────────────────────────────


class TestPullAndCleanDataset:

    @patch("src.pipelines.datasets.save_raw_response")
    @patch("src.pipelines.datasets.save_dataset")
    @patch("src.pipelines.datasets.save_data_dictionary")
    @patch("src.pipelines.datasets.fetch_acs_city")
    def test_returns_dataframe_with_expected_columns(
        self, mock_fetch, mock_save_dd, mock_save_ds, mock_save_raw,
        simple_dataset,
    ):
        mock_fetch.return_value = MOCK_B01003_RESPONSE

        df = pull_and_clean_dataset(simple_dataset, years=[2023])

        assert list(df.columns) == [
            "year", "geography", "total_population", "total_population_moe"
        ]

    @patch("src.pipelines.datasets.save_raw_response")
    @patch("src.pipelines.datasets.save_dataset")
    @patch("src.pipelines.datasets.save_data_dictionary")
    @patch("src.pipelines.datasets.fetch_acs_city")
    def test_converts_string_values_to_numeric(
        self, mock_fetch, mock_save_dd, mock_save_ds, mock_save_raw,
        simple_dataset,
    ):
        mock_fetch.return_value = MOCK_B01003_RESPONSE

        df = pull_and_clean_dataset(simple_dataset, years=[2023])

        assert df.iloc[0]["total_population"] == 577193

    @patch("src.pipelines.datasets.save_raw_response")
    @patch("src.pipelines.datasets.save_dataset")
    @patch("src.pipelines.datasets.save_data_dictionary")
    @patch("src.pipelines.datasets.fetch_acs_city")
    def test_suppressed_moe_becomes_none(
        self, mock_fetch, mock_save_dd, mock_save_ds, mock_save_raw,
        simple_dataset,
    ):
        mock_fetch.return_value = MOCK_B01003_RESPONSE

        df = pull_and_clean_dataset(simple_dataset, years=[2023])

        assert df.iloc[0]["total_population_moe"] is None

    @patch("src.pipelines.datasets.save_raw_response")
    @patch("src.pipelines.datasets.save_dataset")
    @patch("src.pipelines.datasets.save_data_dictionary")
    @patch("src.pipelines.datasets.fetch_acs_city")
    def test_real_moe_preserved(
        self, mock_fetch, mock_save_dd, mock_save_ds, mock_save_raw,
        simple_dataset,
    ):
        mock_fetch.return_value = MOCK_WITH_MOE_RESPONSE

        df = pull_and_clean_dataset(simple_dataset, years=[2023])

        assert df.iloc[0]["total_population_moe"] == 1234

    @patch("src.pipelines.datasets.save_raw_response")
    @patch("src.pipelines.datasets.save_dataset")
    @patch("src.pipelines.datasets.save_data_dictionary")
    @patch("src.pipelines.datasets.fetch_acs_city")
    def test_multiple_years_produces_multiple_rows(
        self, mock_fetch, mock_save_dd, mock_save_ds, mock_save_raw,
        simple_dataset,
    ):
        mock_fetch.return_value = MOCK_B01003_RESPONSE

        df = pull_and_clean_dataset(simple_dataset, years=[2020, 2021, 2022])

        assert len(df) == 3
        assert list(df["year"]) == [2020, 2021, 2022]

    @patch("src.pipelines.datasets.save_raw_response")
    @patch("src.pipelines.datasets.save_dataset")
    @patch("src.pipelines.datasets.save_data_dictionary")
    @patch("src.pipelines.datasets.fetch_acs_city")
    def test_geography_is_baltimore_city(
        self, mock_fetch, mock_save_dd, mock_save_ds, mock_save_raw,
        simple_dataset,
    ):
        mock_fetch.return_value = MOCK_B01003_RESPONSE

        df = pull_and_clean_dataset(simple_dataset, years=[2023])

        assert df.iloc[0]["geography"] == "Baltimore City"

    @patch("src.pipelines.datasets.save_raw_response")
    @patch("src.pipelines.datasets.save_dataset")
    @patch("src.pipelines.datasets.save_data_dictionary")
    @patch("src.pipelines.datasets.fetch_acs_city")
    def test_skips_census_geo_columns(
        self, mock_fetch, mock_save_dd, mock_save_ds, mock_save_raw,
        simple_dataset,
    ):
        """Census returns 'state' and 'county' columns — these should not
        appear in the clean dataset."""
        mock_fetch.return_value = MOCK_B01003_RESPONSE

        df = pull_and_clean_dataset(simple_dataset, years=[2023])

        assert "state" not in df.columns
        assert "county" not in df.columns

    @patch("src.pipelines.datasets.save_raw_response")
    @patch("src.pipelines.datasets.save_dataset")
    @patch("src.pipelines.datasets.save_data_dictionary")
    @patch("src.pipelines.datasets.fetch_acs_city")
    def test_save_false_skips_file_writes(
        self, mock_fetch, mock_save_dd, mock_save_ds, mock_save_raw,
        simple_dataset,
    ):
        mock_fetch.return_value = MOCK_B01003_RESPONSE

        pull_and_clean_dataset(simple_dataset, years=[2023], save=False)

        mock_save_ds.assert_not_called()
        mock_save_dd.assert_not_called()

    @patch("src.pipelines.datasets.save_raw_response")
    @patch("src.pipelines.datasets.save_dataset")
    @patch("src.pipelines.datasets.save_data_dictionary")
    @patch("src.pipelines.datasets.fetch_acs_city")
    def test_raw_response_always_saved(
        self, mock_fetch, mock_save_dd, mock_save_ds, mock_save_raw,
        simple_dataset,
    ):
        """Raw responses are saved even when save=False for clean datasets,
        because the raw layer is the audit trail."""
        mock_fetch.return_value = MOCK_B01003_RESPONSE

        pull_and_clean_dataset(simple_dataset, years=[2023], save=False)

        mock_save_raw.assert_called_once()


# ── TOTAL_POPULATION definition tests ────────────────────────────────────────


class TestTotalPopulationDefinition:
    """Verify the built-in TOTAL_POPULATION dataset is correctly defined."""

    def test_table_id(self):
        assert TOTAL_POPULATION.table_id == "B01003"

    def test_has_estimate_and_moe(self):
        var_names = [c.name for c in TOTAL_POPULATION.columns]
        assert "total_population" in var_names
        assert "total_population_moe" in var_names

    def test_file_name(self):
        assert TOTAL_POPULATION.file_name == "acs1_total_population"


# ── CCD Dataset tests ─────────────────────────────────────────────────────────

from src.pipelines.datasets import (
    CCDDataset,
    ENROLLMENT_CCD,
    pull_and_clean_ccd_dataset,
)

MOCK_CCD_RESPONSE = [
    {"year": 2022, "leaid": "2400090", "enrollment": 76800},
    {"year": 2023, "leaid": "2400090", "enrollment": 75100},
]


def test_ccd_dataset_file_name():
    ds = CCDDataset(leaid="2400090", name="k12_enrollment", title="K-12 Enrollment", description="Test")
    assert ds.file_name == "ccd_k12_enrollment"


def test_pull_and_clean_ccd_returns_dataframe():
    with patch("src.pipelines.datasets.fetch_ccd_district_enrollment") as mock_fetch:
        mock_fetch.return_value = MOCK_CCD_RESPONSE
        df = pull_and_clean_ccd_dataset(ENROLLMENT_CCD, save=False)

    assert list(df.columns) == ["year", "geography", "k12_enrollment"]
    assert len(df) == 2


def test_pull_and_clean_ccd_year_convention():
    """NCES year (start year) should be converted to ending year (+1)."""
    with patch("src.pipelines.datasets.fetch_ccd_district_enrollment") as mock_fetch:
        mock_fetch.return_value = [{"year": 2022, "leaid": "2400090", "enrollment": 76800}]
        df = pull_and_clean_ccd_dataset(ENROLLMENT_CCD, save=False)

    # NCES 2022 = SY 2022-23 → stored as year 2023
    assert df.iloc[0]["year"] == 2023


def test_pull_and_clean_ccd_geography():
    with patch("src.pipelines.datasets.fetch_ccd_district_enrollment") as mock_fetch:
        mock_fetch.return_value = MOCK_CCD_RESPONSE
        df = pull_and_clean_ccd_dataset(ENROLLMENT_CCD, save=False)

    assert (df["geography"] == "Baltimore City").all()

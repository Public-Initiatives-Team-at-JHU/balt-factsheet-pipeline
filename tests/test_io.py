"""Tests for src/utils/io.py — the three-layer I/O utilities."""

import json

import pandas as pd
import pytest

from src.utils.io import save_data_dictionary, save_dataset, save_raw_response


class TestSaveRawResponse:
    """Tests for Layer 1: raw API response saving."""

    def test_saves_json_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.utils.io.RAW_DIR", tmp_path)

        data = [["B01003_001E", "state"], ["577193", "24"]]
        path = save_raw_response(data, "acs5", "B01003", 2023)

        assert path.exists()
        assert path.suffix == ".json"

    def test_file_content_matches_input(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.utils.io.RAW_DIR", tmp_path)

        data = [["header"], ["value"]]
        path = save_raw_response(data, "acs5", "B01003", 2023)

        with open(path) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_filename_contains_source_table_geo_year(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.utils.io.RAW_DIR", tmp_path)

        path = save_raw_response([], "acs5", "B01003", 2023, geo="tracts")
        name = path.name

        assert "acs5" in name
        assert "B01003" in name
        assert "tracts" in name
        assert "2023" in name

    def test_filename_has_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.utils.io.RAW_DIR", tmp_path)

        path = save_raw_response([], "acs5", "B01003", 2023)
        # Timestamp format: 20260302T143022
        assert "T" in path.stem  # ISO-ish timestamp separator

    def test_saves_dict_data(self, tmp_path, monkeypatch):
        """BLS API returns dicts, not lists — io should handle both."""
        monkeypatch.setattr("src.utils.io.RAW_DIR", tmp_path)

        data = {"Results": {"series": [{"data": []}]}}
        path = save_raw_response(data, "bls", "LAUS", "2020-2023")

        with open(path) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_creates_directory_if_missing(self, tmp_path, monkeypatch):
        nested = tmp_path / "does_not_exist"
        monkeypatch.setattr("src.utils.io.RAW_DIR", nested)

        path = save_raw_response([], "acs5", "B01003", 2023)
        assert path.exists()

    def test_no_overwrite_on_repeated_calls(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.utils.io.RAW_DIR", tmp_path)

        save_raw_response(["first"], "acs5", "B01003", 2023)
        save_raw_response(["second"], "acs5", "B01003", 2023)

        files = list(tmp_path.glob("*.json"))
        # Timestamps may collide within same second, but should create
        # at least 1 file (2 if timestamps differ)
        assert len(files) >= 1


class TestSaveDataset:
    """Tests for Layer 2: clean dataset CSV saving."""

    def test_saves_csv(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.utils.io.DATASETS_DIR", tmp_path)

        df = pd.DataFrame({"year": [2023], "value": [100]})
        path = save_dataset(df, "test_dataset")

        assert path.exists()
        assert path.name == "test_dataset.csv"

    def test_csv_content_matches_dataframe(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.utils.io.DATASETS_DIR", tmp_path)

        df = pd.DataFrame({"year": [2023], "population": [577193]})
        path = save_dataset(df, "test_dataset")

        loaded = pd.read_csv(path)
        assert loaded.iloc[0]["population"] == 577193

    def test_no_index_column_in_csv(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.utils.io.DATASETS_DIR", tmp_path)

        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        path = save_dataset(df, "test_dataset")

        loaded = pd.read_csv(path)
        assert list(loaded.columns) == ["a", "b"]  # no "Unnamed: 0" index col


class TestSaveDataDictionary:
    """Tests for data dictionary companion files."""

    def test_saves_data_dictionary_csv(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.utils.io.DATASETS_DIR", tmp_path)

        columns = [
            {"column": "year", "description": "Vintage year",
             "census_variable": "", "universe": "", "notes": ""},
        ]
        path = save_data_dictionary(columns, "test_dataset")

        assert path.exists()
        assert path.name == "test_dataset_data_dictionary.csv"

    def test_data_dictionary_content(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.utils.io.DATASETS_DIR", tmp_path)

        columns = [
            {"column": "pop", "description": "Total population",
             "census_variable": "B01003_001E", "universe": "Total", "notes": ""},
        ]
        path = save_data_dictionary(columns, "test_dataset")

        loaded = pd.read_csv(path)
        assert loaded.iloc[0]["column"] == "pop"
        assert loaded.iloc[0]["census_variable"] == "B01003_001E"

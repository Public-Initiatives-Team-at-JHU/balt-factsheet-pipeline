"""Tests for src/pipelines/msde_report_card.py — MSDE Report Card pipeline."""

from unittest.mock import MagicMock, patch
import io
import zipfile

import pandas as pd
import pytest

from src.pipelines.msde_report_card import (
    ACCOUNTABILITY_DATA,
    ACCOUNTABILITY_DETAILS,
    KNOWN_FILE_IDS,
    download_msde_file,
    discover_file_ids,
    pull_and_clean_msde_dataset,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_accountability_schools_csv():
    """Mock CSV content for accountability schools data."""
    return """Year,LEA,LEA Name,School,School Name,Rating,Total Points Earned Percentage
2025,30,Baltimore City,0101,Test Elementary,3,55.5
2025,30,Baltimore City,0102,Test Middle,2,44.2
"""


@pytest.fixture
def mock_accountability_details_csv():
    """Mock CSV content for accountability details data."""
    return """Year,LEA,LEA Name,School,School Name,Grade Span,Summary Group Title,Indicator Name,Measure Name,Subject Title,Measure Earned Points,Measure Result
2025,30,Baltimore City,0101,Test Elementary,E,All Students,Academic Achievement,Percent Proficient,Mathematics,1.5,35.7
2025,30,Baltimore City,0101,Test Elementary,E,All Students,Academic Achievement,Percent Proficient,English/Language Arts,3.0,60.7
"""


def create_mock_zip(csv_content: str, filename: str) -> bytes:
    """Create a mock ZIP file containing CSV data."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename, csv_content)
    return zip_buffer.getvalue()


# ── Test Known File IDs ───────────────────────────────────────────────────────


def test_known_file_ids_structure():
    """Test that KNOWN_FILE_IDS has correct structure."""
    assert isinstance(KNOWN_FILE_IDS, dict)
    assert len(KNOWN_FILE_IDS) >= 4  # At least 2022-2025

    for year, file_map in KNOWN_FILE_IDS.items():
        assert isinstance(year, int)
        assert 2022 <= year <= 2030  # Reasonable year range
        assert "accountability_data" in file_map
        assert "accountability_details" in file_map
        assert isinstance(file_map["accountability_data"], int)
        assert isinstance(file_map["accountability_details"], int)


def test_known_file_ids_2022_2025():
    """Test that known IDs exist for 2022-2025."""
    required_years = [2022, 2023, 2024, 2025]
    for year in required_years:
        assert year in KNOWN_FILE_IDS, f"Missing file IDs for {year}"


# ── Test File ID Discovery ────────────────────────────────────────────────────


def test_discover_file_ids_uses_known():
    """Test that discover_file_ids uses known IDs when available."""
    target_years = [2022, 2023]
    result = discover_file_ids(target_years, use_known_ids=True)

    assert len(result) == 2
    assert result[2022]["accountability_data"] == KNOWN_FILE_IDS[2022]["accountability_data"]
    assert result[2023]["accountability_details"] == KNOWN_FILE_IDS[2023]["accountability_details"]


def test_discover_file_ids_single_file_type():
    """Test discovering only one file type."""
    target_years = [2025]
    result = discover_file_ids(target_years, file_types=["accountability_data"])

    assert 2025 in result
    assert "accountability_data" in result[2025]
    # Should only have accountability_data, not details
    assert len(result[2025]) == 1


# ── Test File Download ────────────────────────────────────────────────────────


@patch('src.pipelines.msde_report_card.requests.get')
def test_download_msde_file_success(mock_get, tmp_path, mock_accountability_schools_csv):
    """Test successful file download and extraction."""
    # Create mock ZIP response
    zip_content = create_mock_zip(mock_accountability_schools_csv, "2025_Accountability_Schools.csv")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = zip_content
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    # Download to temp path
    output_path = tmp_path / "test_schools.csv"
    result_path = download_msde_file(572, output_path)

    # Verify
    assert result_path == output_path
    assert output_path.exists()

    # Verify CSV content
    df = pd.read_csv(output_path)
    assert len(df) == 2
    assert "School Name" in df.columns


@patch('src.pipelines.msde_report_card.requests.get')
def test_download_msde_file_not_zip(mock_get, tmp_path):
    """Test error handling when response is not a ZIP file."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"Not a ZIP file"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    output_path = tmp_path / "test.csv"

    with pytest.raises(ValueError, match="did not return a valid zip file"):
        download_msde_file(999, output_path)


@patch('src.pipelines.msde_report_card.requests.get')
def test_download_msde_file_http_error(mock_get, tmp_path):
    """Test error handling for HTTP errors."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("HTTP 404")
    mock_get.return_value = mock_response

    output_path = tmp_path / "test.csv"

    with pytest.raises(Exception, match="HTTP 404"):
        download_msde_file(999, output_path)


# ── Test Dataset Definitions ──────────────────────────────────────────────────


def test_accountability_data_definition():
    """Test ACCOUNTABILITY_DATA dataset definition."""
    assert ACCOUNTABILITY_DATA.name == "accountability_schools"
    assert ACCOUNTABILITY_DATA.file_type == "accountability_data"
    assert ACCOUNTABILITY_DATA.start_year == 2022
    assert ACCOUNTABILITY_DATA.file_name == "msde_accountability_schools"

    # Check data dictionary
    dd_rows = ACCOUNTABILITY_DATA.data_dictionary_rows
    assert len(dd_rows) > 0
    assert any(row["column"] == "rating" for row in dd_rows)


def test_accountability_details_definition():
    """Test ACCOUNTABILITY_DETAILS dataset definition."""
    assert ACCOUNTABILITY_DETAILS.name == "accountability_details"
    assert ACCOUNTABILITY_DETAILS.file_type == "accountability_details"
    assert ACCOUNTABILITY_DETAILS.start_year == 2022
    assert ACCOUNTABILITY_DETAILS.file_name == "msde_accountability_details"

    # Check data dictionary
    dd_rows = ACCOUNTABILITY_DETAILS.data_dictionary_rows
    assert len(dd_rows) > 0
    assert any(row["column"] == "indicator_name" for row in dd_rows)


# ── Test Pull and Clean ───────────────────────────────────────────────────────


@patch('src.pipelines.msde_report_card.download_all_years')
def test_pull_and_clean_msde_dataset_schools(mock_download, tmp_path, mock_accountability_schools_csv):
    """Test pulling and cleaning accountability schools data."""
    # Create temporary CSV file
    csv_path = tmp_path / "2025_Accountability_Schools.csv"
    csv_path.write_text(mock_accountability_schools_csv)

    # Mock download to return our temp file
    mock_download.return_value = {
        2025: {"accountability_data": csv_path}
    }

    # Pull and clean
    df = pull_and_clean_msde_dataset(
        ACCOUNTABILITY_DATA,
        years=[2025],
        save=False,
        baltimore_city_only=True,
    )

    # Verify results
    assert len(df) == 2  # 2025 has 2 schools
    assert "year" in df.columns
    assert "school_name" in df.columns
    assert "rating" in df.columns
    assert df["year"].iloc[0] == 2025
    assert int(df["lea"].iloc[0]) == 30  # Baltimore City


@patch('src.pipelines.msde_report_card.download_all_years')
def test_pull_and_clean_msde_dataset_details(mock_download, tmp_path, mock_accountability_details_csv):
    """Test pulling and cleaning accountability details data."""
    # Create temporary CSV file
    csv_path = tmp_path / "2025_Accountability_Detail.csv"
    csv_path.write_text(mock_accountability_details_csv)

    # Mock download to return our temp file
    mock_download.return_value = {
        2025: {"accountability_details": csv_path}
    }

    # Pull and clean
    df = pull_and_clean_msde_dataset(
        ACCOUNTABILITY_DETAILS,
        years=[2025],
        save=False,
        baltimore_city_only=True,
    )

    # Verify results
    assert len(df) == 2  # 2 indicator records
    assert "indicator_name" in df.columns
    assert "measure_name" in df.columns
    assert df["year"].iloc[0] == 2025


@patch('src.pipelines.msde_report_card.download_all_years')
def test_pull_and_clean_filters_baltimore_city(mock_download, tmp_path):
    """Test that Baltimore City filter works correctly."""
    # Create CSV with mixed LEAs
    mixed_csv = """Year,LEA,LEA Name,School,School Name,Rating
2025,30,Baltimore City,0101,Baltimore School,3
2025,03,Baltimore County,0201,County School,4
2025,15,Montgomery,0301,Montgomery School,5
"""
    csv_path = tmp_path / "mixed.csv"
    csv_path.write_text(mixed_csv)

    mock_download.return_value = {
        2025: {"accountability_data": csv_path}
    }

    # With filter
    df_filtered = pull_and_clean_msde_dataset(
        ACCOUNTABILITY_DATA,
        years=[2025],
        save=False,
        baltimore_city_only=True,
    )
    assert len(df_filtered) == 1
    # LEA is loaded as string from CSV, converted to int in pipeline
    assert int(df_filtered["lea"].iloc[0]) == 30

    # Without filter
    df_all = pull_and_clean_msde_dataset(
        ACCOUNTABILITY_DATA,
        years=[2025],
        save=False,
        baltimore_city_only=False,
    )
    assert len(df_all) == 3


@patch('src.pipelines.msde_report_card.download_all_years')
def test_pull_and_clean_multi_year(mock_download, tmp_path):
    """Test pulling multiple years and concatenating."""
    # Create CSV files for two years
    csv_2024 = """Year,LEA,School Name,Rating
2024,30,School A,2
"""
    csv_2025 = """Year,LEA,School Name,Rating
2025,30,School A,3
"""

    path_2024 = tmp_path / "2024.csv"
    path_2025 = tmp_path / "2025.csv"
    path_2024.write_text(csv_2024)
    path_2025.write_text(csv_2025)

    mock_download.return_value = {
        2024: {"accountability_data": path_2024},
        2025: {"accountability_data": path_2025},
    }

    df = pull_and_clean_msde_dataset(
        ACCOUNTABILITY_DATA,
        years=[2024, 2025],
        save=False,
        baltimore_city_only=True,
    )

    # Verify multi-year concatenation
    assert len(df) == 2
    assert set(df["year"]) == {2024, 2025}
    assert df["year"].is_monotonic_increasing  # Should be sorted


# ── Test Error Handling ───────────────────────────────────────────────────────


@patch('src.pipelines.msde_report_card.download_all_years')
def test_pull_and_clean_no_data(mock_download):
    """Test error handling when no data is available."""
    mock_download.return_value = {}  # No data downloaded

    with pytest.raises(ValueError, match="No data loaded"):
        pull_and_clean_msde_dataset(
            ACCOUNTABILITY_DATA,
            years=[2026],  # Future year
            save=False,
        )


@patch('src.pipelines.msde_report_card.download_all_years')
def test_pull_and_clean_missing_lea_column(mock_download, tmp_path):
    """Test error when LEA column is missing."""
    csv_no_lea = """Year,School Name,Rating
2025,Test School,3
"""
    csv_path = tmp_path / "no_lea.csv"
    csv_path.write_text(csv_no_lea)

    mock_download.return_value = {
        2025: {"accountability_data": csv_path}
    }

    with pytest.raises(ValueError, match="'lea' column missing"):
        pull_and_clean_msde_dataset(
            ACCOUNTABILITY_DATA,
            years=[2025],
            save=False,
            baltimore_city_only=True,
        )


# ── Test Data Quality ─────────────────────────────────────────────────────────


def test_known_file_ids_completeness():
    """Test that all known years have both file types."""
    for year, files in KNOWN_FILE_IDS.items():
        assert "accountability_data" in files, f"{year} missing accountability_data"
        assert "accountability_details" in files, f"{year} missing accountability_details"
        assert files["accountability_data"] != files["accountability_details"], \
            f"{year} has duplicate IDs"


def test_file_ids_are_sequential():
    """Test that file IDs increase over years (sanity check)."""
    years = sorted(KNOWN_FILE_IDS.keys())
    prev_id = 0

    for year in years:
        data_id = KNOWN_FILE_IDS[year]["accountability_data"]
        assert data_id > prev_id, f"IDs should increase: {year} ID {data_id} <= {prev_id}"
        prev_id = data_id

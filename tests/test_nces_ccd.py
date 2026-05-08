from unittest.mock import patch, MagicMock
import pytest
from src.pipelines.nces_ccd import fetch_ccd_district_enrollment, EDDATA_BASE_URL

MOCK_DIRECTORY_RESPONSE = {
    "count": 1,
    "next": None,
    "results": [
        {
            "year": 2022,
            "leaid": "2400090",
            "lea_name": "Baltimore City Public Schools",
            "enrollment": 75995,
        }
    ],
}


def test_fetch_returns_list_of_dicts():
    with patch("src.pipelines.nces_ccd.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_DIRECTORY_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = fetch_ccd_district_enrollment(leaid="2400090", start_year=2022, end_year=2022)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["year"] == 2022
    assert result[0]["enrollment"] == 75995


def test_fetch_loops_per_year():
    """One API call per year."""
    with patch("src.pipelines.nces_ccd.requests.get") as mock_get:
        mock_get.return_value = MagicMock(
            json=MagicMock(return_value={
                "count": 1, "next": None,
                "results": [{"year": 2020, "leaid": "2400090", "enrollment": 77856}]
            }),
            raise_for_status=MagicMock()
        )
        result = fetch_ccd_district_enrollment(leaid="2400090", start_year=2020, end_year=2022)

    assert mock_get.call_count == 3  # one call per year: 2020, 2021, 2022


def test_fetch_skips_missing_years():
    """If a year returns no results, it should be skipped without error."""
    def mock_response(url, **kwargs):
        m = MagicMock()
        m.raise_for_status.return_value = None
        if "2020" in url:
            m.json.return_value = {"count": 0, "next": None, "results": []}
        else:
            m.json.return_value = {"count": 1, "next": None, "results": [{"year": 2021, "leaid": "2400090", "enrollment": 77807}]}
        return m

    with patch("src.pipelines.nces_ccd.requests.get", side_effect=mock_response):
        result = fetch_ccd_district_enrollment(leaid="2400090", start_year=2020, end_year=2021)

    assert len(result) == 1
    assert result[0]["year"] == 2021

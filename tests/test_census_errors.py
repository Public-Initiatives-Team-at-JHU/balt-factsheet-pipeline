"""Tests for Census API error handling.

Census requires an API key on every data request. Without one (or with a bad
one) it returns an HTML page with HTTP 200, which used to surface as the
cryptic "Expecting value: line 1 column 1 (char 0)". These tests pin that the
user instead gets a plain-English message saying what to do.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.pipelines import census_acs
from src.pipelines.census_acs import CensusAPIError, census_json, require_census_key
from src.utils import config


def _html_response(title: str, body: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"content-type": "text/html"}
    resp.text = f"<html><head><title>{title}</title></head><body>{body}</body></html>"
    resp.json.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")
    return resp


def _json_response(data) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"content-type": "application/json;charset=utf-8"}
    resp.json.return_value = data
    return resp


class TestCensusJson:

    def test_passes_data_through(self):
        data = [["NAME", "B01003_001E"], ["Baltimore city, Maryland", "568271"]]
        assert census_json(_json_response(data)) == data

    def test_missing_key_explains_how_to_fix(self):
        with pytest.raises(CensusAPIError, match="CENSUS_API_KEY") as exc:
            census_json(_html_response("Missing Key"))
        assert "key_signup" in str(exc.value)

    def test_invalid_key_says_key_is_wrong(self):
        with pytest.raises(CensusAPIError, match="(?i)invalid"):
            census_json(_html_response("Invalid Key"))

    def test_other_html_page_shows_its_title(self):
        with pytest.raises(CensusAPIError, match="Service Unavailable"):
            census_json(_html_response("Service Unavailable"))


class TestRequireKey:

    def test_missing_key_fails_before_any_download(self, monkeypatch):
        monkeypatch.setattr(census_acs, "CENSUS_API_KEY", "")
        with pytest.raises(CensusAPIError, match="key_signup"):
            require_census_key()

    def test_present_key_passes(self, monkeypatch):
        monkeypatch.setattr(census_acs, "CENSUS_API_KEY", "abc123")
        require_census_key()  # no error


class TestFetchSurfacesError:

    def test_fetch_acs_city_raises_clear_error(self, monkeypatch):
        monkeypatch.setattr(census_acs, "CENSUS_API_KEY", "")
        with patch("src.pipelines.census_acs.requests.get", return_value=_html_response("Missing Key")):
            with pytest.raises(CensusAPIError, match="CENSUS_API_KEY"):
                census_acs.fetch_acs_city(["B01003_001E"], 2024)


class TestVintageProbe:

    @pytest.fixture(autouse=True)
    def clear_cache(self, monkeypatch):
        monkeypatch.delenv("ACS1_VINTAGE", raising=False)
        config.latest_acs_vintage.cache_clear()
        yield
        config.latest_acs_vintage.cache_clear()

    def test_html_page_is_not_mistaken_for_a_published_year(self):
        # If Census ever answers the probe with a 200 "Missing Key" page, that
        # must not be read as "this year's data is published".
        with patch("src.utils.config.requests.get", return_value=_html_response("Missing Key")):
            assert config.latest_acs_vintage("acs1") == config.ACS1_FALLBACK_YEAR

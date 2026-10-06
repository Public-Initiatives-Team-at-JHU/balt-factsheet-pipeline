"""Tests for src/utils/config.py — ACS vintage resolution.

The ACS vintage is probed at runtime rather than hardcoded, so the pipeline
picks up a new release (e.g. 2025, delayed pending Commerce disclosure-avoidance
review) without a code change. These tests pin the probe's contract: it must
never guess forward past what Census has published, and must degrade to the
known-good fallback rather than raise.
"""

from unittest.mock import patch

import pytest
import requests

from src.utils import config
from src.utils.config import (
    ACS1_FALLBACK_YEAR,
    ACS5_FALLBACK_YEAR,
    acs1_years,
    latest_acs_vintage,
)


@pytest.fixture(autouse=True)
def clear_vintage_cache(monkeypatch):
    """Vintage resolution is cached per process; isolate each test."""
    monkeypatch.delenv("ACS1_VINTAGE", raising=False)
    monkeypatch.delenv("ACS5_VINTAGE", raising=False)
    latest_acs_vintage.cache_clear()
    yield
    latest_acs_vintage.cache_clear()


def _responder(published_years):
    """Fake requests.get that 200s only for vintages in published_years."""
    def fake_get(url, **kwargs):
        year = int(url.rstrip(".json").split("/data/")[1].split("/")[0])
        resp = requests.Response()
        resp.status_code = 200 if year in published_years else 404
        return resp
    return fake_get


class TestLatestAcsVintage:
    """Runtime resolution of the newest published ACS vintage."""

    def test_returns_newest_published_vintage(self):
        # Census has published through 2024; 2025/2026 do not exist yet.
        with patch.object(config.requests, "get", _responder({2024})):
            assert latest_acs_vintage("acs1") == 2024

    def test_picks_up_new_vintage_without_code_change(self):
        # The whole point: when 2025 lands, the pipeline advances on its own.
        with patch.object(config.requests, "get", _responder({2024, 2025})):
            assert latest_acs_vintage("acs1") == 2025

    def test_falls_back_when_probe_raises(self):
        def boom(url, **kwargs):
            raise requests.ConnectionError("no network")

        with patch.object(config.requests, "get", boom):
            assert latest_acs_vintage("acs1") == ACS1_FALLBACK_YEAR

    def test_never_returns_below_fallback(self):
        # Census API down / all probes 404 — trust the pinned known-good year.
        with patch.object(config.requests, "get", _responder(set())):
            assert latest_acs_vintage("acs1") == ACS1_FALLBACK_YEAR

    def test_resolves_acs5_independently(self):
        with patch.object(config.requests, "get", _responder({2024})):
            assert latest_acs_vintage("acs5") == ACS5_FALLBACK_YEAR

    def test_probes_acs5_path_for_acs5(self):
        seen = []

        def record(url, **kwargs):
            seen.append(url)
            resp = requests.Response()
            resp.status_code = 404
            return resp

        with patch.object(config.requests, "get", record):
            latest_acs_vintage("acs5")

        assert seen, "expected at least one probe"
        assert all("/acs/acs5.json" in url for url in seen)

    def test_caches_result_across_calls(self):
        calls = []
        responder = _responder({2024})

        def counting_get(url, **kwargs):
            calls.append(url)
            return responder(url, **kwargs)

        with patch.object(config.requests, "get", counting_get):
            latest_acs_vintage("acs1")
            first_round = len(calls)
            latest_acs_vintage("acs1")

        assert len(calls) == first_round, "second call should hit the cache"

    def test_rejects_unknown_dataset(self):
        with pytest.raises(ValueError, match="acs3"):
            latest_acs_vintage("acs3")


class TestVintageEnvOverride:
    """An explicit pin makes a run reproducible after a new vintage lands."""

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setenv("ACS1_VINTAGE", "2022")

        def boom(url, **kwargs):
            raise AssertionError("override must not probe the network")

        with patch.object(config.requests, "get", boom):
            assert latest_acs_vintage("acs1") == 2022

    def test_invalid_override_is_ignored(self, monkeypatch):
        monkeypatch.setenv("ACS1_VINTAGE", "not-a-year")

        with patch.object(config.requests, "get", _responder({2024})):
            assert latest_acs_vintage("acs1") == 2024


class TestAcs1Years:
    """Trend year lists derive from the resolved vintage."""

    def test_ends_at_resolved_vintage_and_excludes_2020(self):
        # 2020 ACS 1-Year was never released (COVID collection failure).
        with patch.object(config.requests, "get", _responder({2024, 2025})):
            years = acs1_years(2018)

        assert years == [2018, 2019, 2021, 2022, 2023, 2024, 2025]

    def test_respects_table_specific_start_year(self):
        with patch.object(config.requests, "get", _responder({2024})):
            assert acs1_years(2022) == [2022, 2023, 2024]

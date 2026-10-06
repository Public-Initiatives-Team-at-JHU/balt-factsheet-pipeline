"""Tests for src/utils/provenance.py and the configurable output folder.

Every published output must trace back to the exact code that produced it,
and a mistyped output folder must fail loudly rather than write somewhere
nobody will look.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src.utils import provenance
from src.utils.config import DATA_DIR, PIPELINE_REPO_URL, processed_dir_from_env


def _git_result(stdout: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


class TestPipelineVersion:

    def test_clean_checkout_returns_short_commit(self):
        with patch("subprocess.run", side_effect=[_git_result("a1b2c3d\n"), _git_result("")]):
            assert provenance.pipeline_version() == "a1b2c3d"

    def test_uncommitted_changes_are_flagged(self):
        with patch("subprocess.run", side_effect=[_git_result("a1b2c3d\n"), _git_result(" M src/x.py\n")]):
            assert provenance.pipeline_version() == "a1b2c3d-modified"

    def test_not_a_git_checkout_returns_unknown(self):
        err = subprocess.CalledProcessError(128, "git")
        with patch("subprocess.run", side_effect=err):
            assert provenance.pipeline_version() == "unknown"

    def test_git_not_installed_returns_unknown(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert provenance.pipeline_version() == "unknown"


class TestAddProvenance:

    def test_adds_repo_and_version_columns(self):
        df = pd.DataFrame({"indicator_id": ["poverty_rate", "total_population"]})
        with patch.object(provenance, "pipeline_version", return_value="a1b2c3d"):
            out = provenance.add_provenance(df)
        assert list(out["pipeline_repo"]) == [PIPELINE_REPO_URL] * 2
        assert list(out["pipeline_version"]) == ["a1b2c3d"] * 2

    def test_does_not_modify_input(self):
        df = pd.DataFrame({"indicator_id": ["poverty_rate"]})
        with patch.object(provenance, "pipeline_version", return_value="a1b2c3d"):
            provenance.add_provenance(df)
        assert list(df.columns) == ["indicator_id"]


class TestOutputDir:

    def test_defaults_to_processed_folder(self, monkeypatch):
        monkeypatch.delenv("FACTSHEET_OUTPUT_DIR", raising=False)
        assert processed_dir_from_env() == DATA_DIR / "02 processed"

    def test_env_var_overrides(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FACTSHEET_OUTPUT_DIR", str(tmp_path))
        assert processed_dir_from_env() == tmp_path

    def test_expands_home_directory(self, monkeypatch):
        monkeypatch.setenv("FACTSHEET_OUTPUT_DIR", "~/Fact Sheet")
        assert processed_dir_from_env() == Path.home() / "Fact Sheet"

    def test_missing_folder_fails_loudly(self, monkeypatch, tmp_path):
        missing = tmp_path / "typo"
        monkeypatch.setenv("FACTSHEET_OUTPUT_DIR", str(missing))
        with pytest.raises(FileNotFoundError, match="FACTSHEET_OUTPUT_DIR"):
            provenance.check_output_dir(missing)

    def test_default_folder_needs_no_check(self, monkeypatch, tmp_path):
        monkeypatch.delenv("FACTSHEET_OUTPUT_DIR", raising=False)
        provenance.check_output_dir(tmp_path / "not-yet-created")  # no error

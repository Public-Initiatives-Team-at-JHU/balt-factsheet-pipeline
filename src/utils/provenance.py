"""
Provenance: tie every published output back to the code that produced it.

Outputs are published to SharePoint while the code lives on GitHub. Each
metadata file gets two columns so anyone holding a CSV can find the exact
version of the code behind it:

  pipeline_repo     the GitHub repository URL
  pipeline_version  the git commit, e.g. "a1b2c3d". A "-modified" suffix
                    means the run used code with uncommitted edits, so the
                    commit alone doesn't fully describe it.

To see the code for a version, open {pipeline_repo}/commit/{pipeline_version}
(dropping any "-modified" suffix).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pandas as pd

from src.utils.config import PIPELINE_REPO_URL, PROJECT_ROOT


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return result.stdout.strip()


def pipeline_version() -> str:
    """Short git commit of the running code, or "unknown" outside a git checkout."""
    try:
        commit = _git("rev-parse", "--short", "HEAD")
        uncommitted = _git("status", "--porcelain", "--untracked-files=no")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "unknown"
    return f"{commit}-modified" if uncommitted else commit


def add_provenance(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with pipeline_repo and pipeline_version columns."""
    out = df.copy()
    out["pipeline_repo"] = PIPELINE_REPO_URL
    out["pipeline_version"] = pipeline_version()
    return out


def check_output_dir(output_dir: Path) -> None:
    """Fail loudly if FACTSHEET_OUTPUT_DIR points at a folder that doesn't exist.

    Without this, a typo in the path would silently create a new folder and the
    outputs would never reach SharePoint. The default folder is created as needed.
    """
    if os.environ.get("FACTSHEET_OUTPUT_DIR") and not output_dir.is_dir():
        raise FileNotFoundError(
            f"FACTSHEET_OUTPUT_DIR is set to '{output_dir}', but that folder doesn't exist. "
            "Check the path, and that OneDrive has finished syncing the SharePoint folder."
        )

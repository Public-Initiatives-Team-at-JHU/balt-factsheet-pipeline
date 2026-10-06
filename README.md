# Baltimore Fact Sheet Data Pipeline

This code automatically pulls public data about Baltimore City from Census, BLS, the Maryland State Department of Education, Baltimore Police and federal education data, and turns it into a set of fact sheet numbers (population, poverty, unemployment, crime, housing, schools and more). The results are CSV files that the Public Impact Initiatives Power BI dashboard reads.

**You don't need to read the code to use it.** Most of the time you'll run one command and refresh Power BI.

---

## 1. One-time setup

You need Python 3.9 or newer. In a terminal, from this folder:

```bash
pip install -r requirements.txt
```

**Optional, but recommended: free API keys.** The pipeline works without them, but keys raise the daily limits on how much data you can download.

- Census: https://api.census.gov/data/key_signup.html
- BLS: https://data.bls.gov/registrationEngine/

Each person should register their own keys. Then set them in your terminal before running:

```bash
export CENSUS_API_KEY="your-census-key"
export BLS_API_KEY="your-bls-key"
```

Never paste keys into the code or commit them to GitHub.

## 2. Update the fact sheet

```bash
python3 -m src.run_factsheet
```

This takes a few minutes. It downloads the latest data, recalculates every metric, checks the results, and prints a summary. At the end, look for the **"Validating outputs"** line:

- `All validation checks passed.` means you're good to go.
- If it lists **ERROR** lines, don't publish the new numbers yet. Something in the source data looks wrong (missing years, impossible values). **WARN** lines are worth reading but usually fine.

If a Census download fails, the run stops with an `ERROR`. Census is the core of the fact sheet, so wait a bit and run it again. If any other source is temporarily down (BLS, crime, schools), the run prints `FAILED` for that source and keeps going without it.

**Optional:** regenerate the trend charts in `data/visualizations/`:

```bash
python3 scripts/plot_factsheet.py
```

## 3. Where the results go

Everything Power BI needs is in `data/processed/`:

| File | What's in it |
|------|--------------|
| `baltimore_factsheet.csv` | The fact sheet: one row per year, one column per metric |
| `baltimore_factsheet_long.csv` | The same numbers in "long" format (one row per metric per year), plus breakdowns by race/ethnicity |
| `baltimore_factsheet_metadata.csv` | For every metric: plain-English definition, formula, source, link and caveats |
| `baltimore_factsheet_equity_metadata.csv` | The same, for the race/ethnicity breakdowns |

The metadata files are the place to answer "where does this number come from?"

Two other folders are useful if you want to dig in:

- `data/datasets/`: the cleaned source data, one CSV per table, each with a `_data_dictionary.csv` explaining every column. Fine to use for your own analysis.
- `data/raw/`: the exact data each source sent back, saved with timestamps. If a number ever looks wrong, this is where to trace it.

## 4. When to update

| Source | Metrics | New data released |
|--------|---------|-------------------|
| Census ACS 1-Year | Population, income, poverty, education, housing, race/ethnicity | Every September (covers the prior year) |
| Census Population Estimates | Annual population estimate | Every spring (city/county estimates) |
| BLS | Unemployment rate | Monthly |
| Baltimore Police (Open Baltimore) | Crime rates, homicides | Ongoing |
| MSDE Report Card | School ratings and accountability scores | Annually, in winter |
| NCES (via Urban Institute) | K-12 enrollment | Annually |

The pipeline detects the newest Census year on its own. You don't need to change any settings when new ACS data comes out.

> **Note (October 2026):** Census has not yet released the 2025 ACS data and hasn't announced a date, so ACS-based numbers currently stop at 2024. They'll update on the next run after Census publishes.

## 5. Making changes

Common changes, and where to make them:

- **See exactly how a number is calculated:** open `src/pipelines/metrics.py` and search for the metric's name. Each metric is one block containing its formula, source and caveats.
- **Add or remove a fact sheet metric:** in `src/pipelines/metrics.py`, copy a similar metric block and adjust it, then add it to (or remove it from) the `ALL_FACTSHEET_METRICS` list at the bottom of the file.
- **Pull a new Census table:** add a definition block in `src/pipelines/datasets.py`, modeled on an existing one.
- **Settings (years, keys):** `src/utils/config.py`.

Each of these files starts with a short "New to this code?" note.

**After any change, run the tests:**

```bash
pytest
```

The tests check that every calculation still produces the right answer. They use saved sample data, so they don't download anything. You don't need to read or edit them: if they all pass, your change didn't break anything. If some fail, the message names the metric or dataset that broke.

## Folder guide

```
src/run_factsheet.py   The one command that runs everything
src/pipelines/         One file per data source, plus datasets.py and metrics.py
src/utils/             Settings (config.py), file saving and quality checks
scripts/               Chart generation
tests/                 Automated checks (run with `pytest`)
data/                  Downloaded and processed data
docs/                  Reference files: BNIA indicator list, tract → CSA crosswalks
archive/               Development history: verification reports and one-off scripts. Not needed day to day.
```

`CLAUDE.md` is detailed project context for developers and AI coding assistants, including the planned next phases (neighborhood-level data and JHU impact data).

## Data sources

- **Census American Community Survey (ACS) 1-Year:** city-level demographics, income, poverty, education, housing. https://www.census.gov/programs-surveys/acs
- **Census Population Estimates Program:** official annual population estimates. https://www.census.gov/programs-surveys/popest.html
- **BLS Local Area Unemployment Statistics:** monthly unemployment rate. https://www.bls.gov/lau/
- **Open Baltimore, BPD crime data:** Part 1 crime (older SRS system, through 2024) and NIBRS (2022 onward; the two overlap in 2022–2024 for comparison). https://data.baltimorecity.gov/
- **Maryland State Department of Education Report Card:** school ratings. https://reportcard.msde.maryland.gov/ (details in `src/pipelines/README_MSDE.md`)
- **NCES Common Core of Data:** K-12 enrollment, via the Urban Institute Education Data API. https://educationdata.urban.org/

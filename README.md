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
python3 -m scripts.plot_factsheet
```

## 3. Where the results go

Everything Power BI needs is in `data/02 processed/`:

| File | What's in it |
|------|--------------|
| `baltimore_factsheet.csv` | The fact sheet: one row per year, one column per metric |
| `baltimore_factsheet_long.csv` | The same numbers in "long" format (one row per metric per year), plus breakdowns by race/ethnicity |
| `baltimore_factsheet_metadata.csv` | For every metric: plain-English definition, formula, source, link and caveats |
| `baltimore_factsheet_equity_metadata.csv` | The same, for the race/ethnicity breakdowns |

The metadata files are the place to answer "where does this number come from?"

Two other folders are useful if you want to dig in:

- `data/01 clean/`: the cleaned source data, one CSV per table, each with a `_data_dictionary.csv` explaining every column. Fine to use for your own analysis.
- `data/00 raw/`: the exact data each source sent back, saved with timestamps. If a number ever looks wrong, this is where to trace it.

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

## 6. Optional: using Claude Code

**You don't need any AI tools to run or maintain this pipeline.** Everything above works on its own.

This repository was built with [Claude Code](https://claude.com/claude-code), an AI coding assistant from Anthropic that runs in your terminal. It can read the code, run commands and make edits for you. If your team has access to it, it can be useful for people who are less comfortable with code: you describe what you want in plain English, and it does the work and explains it.

### What `CLAUDE.md` is for

`CLAUDE.md` is a briefing document for Claude. Whenever Claude Code is started in this folder, it reads `CLAUDE.md` first, so it already knows the project's background without anyone re-explaining it:

- the project's goals and the three workstreams (fact sheet, JHU impact data, neighborhood deep dives)
- who the dashboard's users are and what they need
- the data sources, key settings and known caveats (for example, the delayed 2025 ACS release)
- data quality rules the code must follow (keep margins of error, don't average pre-computed rates, check Census variable codes each year)
- planned next phases that aren't built yet

People can read it too. It's the most detailed description of the project's intent, beyond the how-to in this README.

**Keep it current.** When a decision changes (official priority-area boundaries are confirmed, a metric is added or dropped, a data source changes), update `CLAUDE.md`. An out-of-date briefing leads Claude to make wrong assumptions. You can ask Claude to update it for you, e.g. *"Update CLAUDE.md: the priority area boundaries are now official."*

### Getting started

1. Install Claude Code by following the instructions at https://claude.com/claude-code. You'll need a Claude account. Check with JHU IT about which AI tools and accounts are approved.
2. In a terminal, go to this folder and type `claude`.
3. Ask for what you want in plain English.

Example requests:

- *"Run the fact sheet pipeline and tell me whether validation passed."*
- *"New ACS data came out. Update the fact sheet and summarize which numbers changed the most."*
- *"How is the poverty rate calculated, and what are its caveats?"*
- *"Add a fact sheet metric for the share of households with no vehicle, from ACS table B25044."*
- *"The tests are failing. What broke?"*

### Ground rules

- **Review before you keep anything.** Claude can make mistakes. Read its summary of what it changed, run `pytest`, and check that the numbers look sensible before publishing.
- **Never paste API keys, passwords, or confidential data into the chat.** This matters especially for the JHU internal data planned for later phases (HR, finance, development). Follow JHU's policies on what data can be shared with AI tools.
- **Claude doesn't replace checking against sources.** For any number going into a presentation, the source link in the metadata file is the authority.

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

`CLAUDE.md` is detailed project background, read automatically by Claude Code (see section 6) and useful for people too. It covers the planned next phases (neighborhood-level data and JHU impact data).

## Data sources

- **Census American Community Survey (ACS) 1-Year:** city-level demographics, income, poverty, education, housing. https://www.census.gov/programs-surveys/acs
- **Census Population Estimates Program:** official annual population estimates. https://www.census.gov/programs-surveys/popest.html
- **BLS Local Area Unemployment Statistics:** monthly unemployment rate. https://www.bls.gov/lau/
- **Open Baltimore, BPD crime data:** Part 1 crime (older SRS system, through 2024) and NIBRS (2022 onward; the two overlap in 2022–2024 for comparison). https://data.baltimorecity.gov/
- **Maryland State Department of Education Report Card:** school ratings. https://reportcard.msde.maryland.gov/ (details in `src/pipelines/README_MSDE.md`)
- **NCES Common Core of Data:** K-12 enrollment, via the Urban Institute Education Data API. https://educationdata.urban.org/

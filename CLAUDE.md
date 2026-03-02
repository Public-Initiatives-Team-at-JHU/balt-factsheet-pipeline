# JHU Public Impact Data Pipelines

## Project Overview

Build data pipelines for the JHU Public Impact Initiatives team's internal dashboard, hosted on SharePoint with Power BI visualizations. The dashboard serves JHU leadership and communications staff who need quick access to facts about Baltimore and Hopkins' community impact — for presentations, press conferences, elected official meetings, and storytelling.

The project has **three workstreams**, prioritized in this order:

### Workstream 1: Baltimore Fact Sheet (March-April 2026 delivery)
Automate a currently-manual "Baltimore fact sheet" with **7-8 core statistics** about Baltimore City. This is city-level data (not neighborhood), refreshed on varying cadences (annual, monthly, quarterly). Pipeline these from public APIs so they auto-update. Target: last 5-10 years of trend data, starting from 2020 for consistency.

**Core fact sheet stats (confirmed):**
- Population (annual, Census Population Estimates Program)
- Unemployment rate (monthly, BLS Local Area Unemployment Statistics)
- Poverty rate (annual, ACS)
- Additional 4-5 stats TBD — likely from the existing fact sheet (median income, education attainment, crime rate, housing)

### Workstream 2: JHU Impact Data (longer timeline)
Internal Hopkins data measuring community contributions — employee/student residence locations, procurement, small business spending, fellowships/grants. Data comes from internal sources (HR via president's liaison, finance, development office). Format and access method unknown — could be numbers, CSVs, or point files. This will take longer to stand up because data acquisition is still being figured out.

### Workstream 3: Neighborhood/Topic Deep Dives (ongoing)
Detailed point-level data for specific topics (e.g., vacancy — Peter is already working on BBRC vacant building coalition data). May expand to other topics. Uses geographic priority areas around Hopkins campuses.

## Key Context

- **Team:** Seema (lead), Peter (data analyst, building Python notebooks + Power BI dashboards), Justin (consultant — pipelines, architecture, user research)
- **Platform:** SharePoint site for the Public Impact Initiatives team, with Power BI dashboards embedded in pages. ArcGIS plugin for Power BI for mapping.
- **Users:** JHU leadership (president's office), communications/comms staff, compliance, development office, finance. Primary use case is storytelling + rapid fact-finding, not raw data exploration.
- **Dashboard UX:** Combination of preloaded visualizations AND chatbot functionality with preloaded questions. Most users want facts + sources, not raw data.
- **Source metadata:** Each data source needs documentation (what it is, why you'd use it, caveats). Internal education is a goal — people should understand and be able to agree on the sources.
- **Geographic priority areas:** East Baltimore, Homewood, Peabody, Carey School of Business, Bayview. Shapefile for these boundaries exists (unofficial, not yet confirmed as official). Mount Washington excluded. Also interested in Remington and EBDI comparisons.
- **BNIA:** Can't use BNIA's published data directly because of ~1 year lag. Use the same underlying sources but pull more current data.
- **Peter's existing work:** Python notebooks pulling from Open Baltimore API (vacancy focus). Code review needed. Acquisition log started in SharePoint. Uses Power BI with ArcGIS plugin.
- **Federal data risk:** Some federal datasets may no longer exist or be trustworthy given current political climate. Census and BLS are assumed reliable for now but worth monitoring.

## Architecture

```
src/
  pipelines/
    bls.py               # BLS LAUS API for monthly unemployment
    census_acs.py        # ACS 5-Year API for poverty, income, demographics
    census_pop.py        # Population Estimates Program (annual pop estimates)
    open_baltimore.py    # Socrata API for crime, demolitions, vacants
    education.py         # BCPS / MSDE data (manual download + parse)
    health.py            # Health dept data (scrape/parse)
    elections.py         # Voter registration/turnout
    hud.py               # Housing voucher data from HUD
  crosswalk/
    tract_to_csa.py      # Census tract → CSA crosswalk logic
    school_to_csa.py     # School catchment → CSA mapping
    geocode_to_csa.py    # Lat/lon point → CSA assignment
  transforms/
    aggregation.py       # Weighted averaging, summing, rate calculation
    derived.py           # Computed indicators (diversity index, pop change)
  output/
    sharepoint.py        # Upload to SharePoint document library
    dashboard_data.py    # Format for Power BI / dashboard consumption
  utils/
    config.py            # API keys, FIPS codes, year parameters
    validation.py        # Data quality checks
data/
  raw/                   # Downloaded source files (gitignored)
  crosswalks/            # Tract-to-CSA and other mapping files
  processed/             # Pipeline outputs
  boundaries/            # Shapefiles — CSA boundaries, Hopkins priority areas
docs/
  BNIA_Indicator_Data_Sources.xlsx  # Full 63-indicator reference with table IDs + API endpoints
```

## Key Constants

```python
# Baltimore City FIPS
STATE_FIPS = "24"        # Maryland
COUNTY_FIPS = "510"      # Baltimore City (independent city)
COUNTY_FIPS_FULL = "24510"  # Combined for BLS queries

# Census API
CENSUS_API_BASE = "https://api.census.gov/data/{year}/acs/acs5"
CENSUS_PEP_BASE = "https://api.census.gov/data/{year}/pep/population"
CENSUS_API_KEY = ""      # Get at api.census.gov/data/key_signup.html — optional but recommended

# BLS API
BLS_API_BASE = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_LAUS_SERIES = "LAUST245100000000003"  # Baltimore City unemployment rate (LAUS)
BLS_API_KEY = ""  # Get at https://data.bls.gov/registrationEngine/ — optional, higher limits

# ACS vintage — use 5-Year estimates
DEFAULT_ACS_YEAR = 2023  # Latest available; produces 2019-2023 estimates

# Open Baltimore (Socrata)
OPEN_BALT_BASE = "https://data.baltimorecity.gov/resource"

# BNIA CSAs
NUM_CSAS = 55  # Baltimore has 55 Community Statistical Areas

# Trend data range
TREND_START_YEAR = 2020  # Per Seema: start all trend data from 2020 for consistency
```

## Build Order

### Phase 1: Baltimore Fact Sheet (target: March-April 2026)

This is the quick win. City-level data, simple pipelines, immediate value.

1. **BLS unemployment pipeline** — Monthly data, BLS LAUS API. Baltimore City series ID: `LAUST245100000000003`. Pull 2020-present.
2. **Census population pipeline** — Annual population estimate from Population Estimates Program (PEP). Baltimore City. Pull 2020-present.
3. **Census ACS core stats** — Poverty rate (B17001/B17021), median household income (B19013), education attainment (B15003). City-level (not tract — simpler than CSA aggregation). Pull last 5 ACS vintages.
4. **Additional fact sheet stats** — TBD based on what Seema confirms from the existing fact sheet. Likely crime rate (Open Baltimore), housing stats.
5. **Power BI dashboard** — Embed in SharePoint page. Preloaded visualizations with trend lines. Source metadata displayed alongside each stat.
6. **Source documentation** — For each data source: what it is, update frequency, why it's authoritative, caveats.

### Phase 2: Expanded Indicators (after fact sheet ships)

Build out the full 63 BNIA indicators for neighborhood-level analysis. This requires the tract-to-CSA crosswalk infrastructure.

1. **Crosswalk infrastructure** — tract-to-CSA mapping, spatial join utilities
2. **Census/ACS pipeline** — 40 indicators at tract level, aggregated to CSA
3. **Open Baltimore pipeline** — crime + housing indicators, geocode to CSA
4. **Education + health pipelines** — manual download + parse
5. **Geographic filtering** — Hopkins priority area boundaries for campus-adjacent analysis
6. **Remaining pipelines** — elections, HUD, lead, TANF (as data becomes available)

### Phase 3: JHU Impact Data

Dependent on internal data access. Build as data becomes available.

1. **Employee/student residence mapping** — Source: HR via president's liaison. Format TBD.
2. **Procurement / small business spending** — Source: finance. Format TBD.
3. **Fellowships, grants** — Source: development office. Format TBD.

## Data Sources — Phase 1 (Baltimore Fact Sheet)

### BLS Local Area Unemployment Statistics (LAUS)

Monthly unemployment rate for Baltimore City.

```python
import requests

def fetch_bls_unemployment(start_year=TREND_START_YEAR, end_year=2025):
    """Fetch monthly Baltimore City unemployment rate from BLS LAUS."""
    url = BLS_API_BASE
    payload = {
        "seriesid": [BLS_LAUS_SERIES],
        "startyear": str(start_year),
        "endyear": str(end_year),
    }
    if BLS_API_KEY:
        payload["registrationkey"] = BLS_API_KEY
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return data["Results"]["series"][0]["data"]
```

BLS API returns JSON with year, period (M01-M12), and value. Free tier: 25 requests/day, 10 years max per request. Registered: 500 requests/day, 20 years.

### Census Population Estimates Program (PEP)

Annual population estimate for Baltimore City. Released every July for the prior year.

```python
def fetch_population_estimate(year):
    """Fetch annual population estimate for Baltimore City."""
    url = f"https://api.census.gov/data/{year}/pep/population"
    params = {
        "get": "POP_2020,POP_{year},NAME",  # Variable names vary by vintage
        "for": "county:510",
        "in": "state:24",
    }
    resp = requests.get(url, params=params)
    return resp.json()
```

Note: PEP variable names change each vintage year. Check the variables endpoint for the target year.

### Census ACS (City-Level for Fact Sheet)

For the fact sheet, pull at **county level** (Baltimore City = county 510), not tract level. This avoids the CSA crosswalk entirely.

```python
def fetch_acs_city_level(variables, year=DEFAULT_ACS_YEAR):
    """Fetch ACS data for Baltimore City as a whole (no tract breakdown)."""
    url = CENSUS_API_BASE.format(year=year)
    params = {
        "get": ",".join(variables),
        "for": "county:510",
        "in": "state:24",
    }
    if CENSUS_API_KEY:
        params["key"] = CENSUS_API_KEY
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()
```

Key tables for fact sheet:
- **B17021** or **S1701**: Poverty rate (city-level)
- **B19013**: Median household income
- **B15003**: Education attainment (HS diploma, Bachelor's+)

## Data Sources — Phase 2 (Full BNIA Indicators)

See `docs/BNIA_Indicator_Data_Sources.xlsx` for the complete reference (63 indicators with table IDs, variable codes, API endpoints, geographic levels, crosswalk requirements, and confidence ratings).

### Census/ACS Pipeline — 40 indicators, HIGH confidence

Single API, single geography (tract), single crosswalk. Bulk of the Phase 2 work.

**ACS Tables used:**

| Table | Indicators | What It Covers |
|-------|-----------|----------------|
| B25091 | Affordability Index - Mortgage | Monthly owner costs as % of HH income |
| B25070 | Affordability Index - Rent | Gross rent as % of HH income |
| B25010 | Average Household Size | Avg persons per occupied unit |
| B19013 | Median Household Income | Median HH income (inflation-adjusted $) |
| B01001 | Age cohorts (5 indicators) | Pop by age: <5, 5-17, 18-24, 25-64, 65+ |
| B01003 | Total Population, Pop Change | Total pop; compare across decennial/ACS |
| B03002 | Race/ethnicity (6 indicators) | Hispanic/Latino origin by race |
| B08301 | Commute mode (4 indicators) | Drove alone, transit, walk, work-from-home |
| B08303 | Long commute (>45 min) | Travel time to work distribution |
| B11005 | HH with children under 18 | Households by presence of children |
| B15003 | Education attainment (2 indicators) | Less than HS, Bachelor's+ |
| B17001 | Child poverty | Poverty status by age |
| B17010 | Family poverty | Poverty status of families |
| B19001 | Income brackets (5 indicators) | HH income distribution buckets |
| B23001 | Employment (3 indicators) | Employed, unemployed, not in labor force (16-64) |
| B23025 | Unemployment rate | Employment status (simplified) |
| B25044 | No vehicles available | Vehicles available per HH |
| B28002 | No internet at home | Internet subscription status |
| B22010 | SNAP recipients | SNAP/food stamps (ACS alternative to state data) |

**API call pattern (tract-level for CSA aggregation):**
```python
def fetch_acs_tracts(table_id, variables, year=DEFAULT_ACS_YEAR):
    """Fetch ACS data for all Baltimore City tracts."""
    url = CENSUS_API_BASE.format(year=year)
    params = {
        "get": ",".join(variables),
        "for": "tract:*",
        "in": f"state:{STATE_FIPS} county:{COUNTY_FIPS}",
    }
    if CENSUS_API_KEY:
        params["key"] = CENSUS_API_KEY
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    return data[0], data[1:]
```

**CRITICAL: Variable code verification.** Before building each table's pipeline, verify variable codes against the Census API groups endpoint:
```
https://api.census.gov/data/{year}/acs/acs5/groups/{TABLE_ID}.html
```
Variable codes can shift between ACS vintages. For example, "drove alone" in B08301 may be `_002E` or `_003E` depending on year.

**Computed indicators:**
- Racial Diversity Index (row 163): Derived from B03002 race/ethnicity shares using a diversity formula (likely Simpson's or Shannon index — check BNIA methodology docs)
- Population Change (row 127): Requires comparing B01003 across two time periods (decennial census vs ACS)

### Open Baltimore / Crime Pipeline — HIGH confidence

Socrata SODA API. Incident-level data with lat/lon → geocode to CSA.

| Indicator | Socrata Dataset | Notes |
|-----------|----------------|-------|
| Gun-related homicides per 1K | BPD Part 1 Victim Based Crime | Filter: description contains homicide + firearm |
| Shootings per 1K | BPD Part 1 Victim Based Crime | Filter: shooting |
| Part 1 crime rate per 1K | BPD Part 1 Victim Based Crime | All Part 1 crimes |
| Property crime rate per 1K | BPD Part 1 Victim Based Crime | Filter: property crimes |
| Violent crime rate per 1K | BPD Part 1 Victim Based Crime | Filter: violent crimes |
| Demolition permits per 1K | Baltimore City permits | Filter: demolition permits |
| Vacant properties (city-owned) | DHCD vacants dataset | Address-level |

```python
def fetch_socrata(dataset_id, where_clause=None, limit=50000):
    url = f"{OPEN_BALT_BASE}/{dataset_id}.json"
    params = {"$limit": limit}
    if where_clause:
        params["$where"] = where_clause
    resp = requests.get(url, params=params)
    return resp.json()
```

### Other Pipelines — MEDIUM to LOW confidence

| Pipeline | Indicators | Source | Challenge |
|----------|-----------|--------|-----------|
| Education | HS completion/dropout, chronic absence, kindergarten readiness | MSDE Report Card | No API; school-to-CSA crosswalk needed |
| Health | Infant mortality, life expectancy | Balt City Health Dept | No API; already at CSA level |
| Elections | Voter registration %, turnout % | Board of Elections | Precinct-to-CSA crosswalk; data may cost $75+ |
| HUD | Housing vouchers per 1K rental units | HUD Picture of Subsidized Housing | Census tract or city-level |
| Lead | Children tested for lead | MD Dept of Environment | Data request required; privacy restrictions |
| TANF | Families receiving TANF | MD DHS | Data request to state; likely city-level only |
| Home sales | Median price, number sold | First American (proprietary) | No public API. BNIA buys this data. |
| Baltimore Area Survey | Community sentiment | 21st Century Cities / JHU | Data on GitHub; requesting Hopkins-campus-area slice |

## Crosswalk: Census Tract → CSA

Critical for Phase 2. Not needed for Phase 1 (city-level fact sheet).

**BNIA maintains the official crosswalk.** Get it from:
- BNIA's Vital Signs open data: https://vital-signs-bniajfi.hub.arcgis.com/
- Or request directly from BNIA

The crosswalk maps each of Baltimore City's ~200 census tracts to one of 55 CSAs. Some tracts split across CSAs (partial assignment).

**Aggregation rules depend on the indicator type:**
- **Counts** (e.g., total population): Sum tract values within each CSA
- **Rates/percentages** (e.g., poverty rate): Weighted average using appropriate denominator (total pop, total HH, etc.)
- **Medians** (e.g., median HH income): Cannot simply average medians. Use tract-level distributions or population-weighted approximation
- **Averages** (e.g., avg HH size): Weight by number of occupied housing units

```python
def aggregate_to_csa(tract_df, crosswalk_df, value_col, weight_col, agg_type="weighted_avg"):
    merged = tract_df.merge(crosswalk_df, on="tract_fips")
    if agg_type == "sum":
        return merged.groupby("csa_name")[value_col].sum()
    elif agg_type == "weighted_avg":
        merged["weighted"] = merged[value_col] * merged[weight_col]
        grouped = merged.groupby("csa_name")
        return grouped["weighted"].sum() / grouped[weight_col].sum()
```

## Geographic Priority Areas

Hopkins has ~7 campus/facility locations. The priority areas for neighborhood-level analysis are:
- East Baltimore (Johns Hopkins Hospital / School of Medicine)
- Homewood (main campus)
- Peabody
- Carey School of Business
- Bayview
- (Mount Washington excluded — isolated, no community engagement relevance)

A shapefile with these boundaries exists in the SharePoint data resources folder. These are **unofficial** and not yet confirmed as the team's official boundary definitions. Seema is working to get agreement.

For neighborhood comparison views, Remington and EBDI are of particular interest.

## Output Format

Power BI dashboards embedded in the SharePoint site. Each dashboard page should show:
- Preloaded visualizations (trend lines, bar charts)
- Source attribution and metadata for each stat
- Option for chatbot-style Q&A with preloaded questions

Data schema (flat table, one row per observation):
```
geography | indicator_name | value | year | period | source | source_url | last_updated
```

Where `geography` is "Baltimore City" for Phase 1, and CSA name for Phase 2. `period` captures the cadence (e.g., "2024-M03" for monthly BLS, "2019-2023" for 5-year ACS).

## Environment

- Python 3.10+
- Key packages: `requests`, `pandas`, `geopandas`, `openpyxl`
- For spatial joins (geocode→CSA): `geopandas`, `shapely`
- For Socrata: `sodapy` (optional convenience wrapper)
- For SharePoint upload: `Office365-REST-Python-Client` or `shareplum`
- For Power BI: data saved as CSV/Excel to SharePoint document library; Power BI connects to files

## Data Quality Rules

- All Census variables must be verified against the groups endpoint for the target ACS year before use
- Null/missing tract data should be flagged, not silently dropped
- MOE (margin of error) columns from ACS should be captured alongside estimates
- Population denominators must match the indicator's definition (e.g., "per 1,000 residents" vs "per 1,000 households")
- CSA aggregation should preserve the denominator for rate recalculation, not average pre-computed rates
- Log all API responses and transformation steps for reproducibility
- Multi-year pulls should use consistent methodology across all years in the trend

## References

- Census API docs: https://www.census.gov/data/developers/data-sets/acs-5year.html
- Census variable lookup: https://api.census.gov/data/{year}/acs/acs5/groups.html
- Census PEP: https://www.census.gov/data/developers/data-sets/popest-popproj/popest.html
- BLS LAUS: https://www.bls.gov/lau/
- BLS API: https://www.bls.gov/developers/
- BNIA Vital Signs: https://vital-signs-bniajfi.hub.arcgis.com/
- Open Baltimore: https://data.baltimorecity.gov/
- Maryland Report Card: https://reportcard.msde.maryland.gov/
- HUD Picture of Subsidized Housing: https://www.huduser.gov/portal/datasets/assthsg.html
- Baltimore Area Survey: https://21cc.jhu.edu/baltimore-area-survey/

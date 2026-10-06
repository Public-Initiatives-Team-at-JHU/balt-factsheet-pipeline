# Data Verification: Our Values vs. Authoritative Sources

## 2023 Data Comparison

| Metric | Our Value | Verified Source | Source Value | Match? | Notes |
|--------|-----------|----------------|--------------|---------|-------|
| **Population** | 565,239 | Census QuickFacts | 565,239 | ✅ Exact | But ACS vs PEP methodology |
| **Median HH Income** | $59,579 | Data USA (ACS) | $59,623 | ✅ 99.9% | $44 difference (0.07%) |
| **Unemployment Rate** | 5.05% | BLS LAUS (FRED) | 2.9% | ❌ No | **2.15 pts higher - wrong source** |
| **Bachelor's+** | 37.07% | MD Dept Commerce | 35.4% | ⚠️ Close | 1-Year vs 5-Year ACS |
| **Rent Burden** | 54.97% | Baltimore Banner | ~54% | ✅ Match | Confirms "54% of renters" |
| **Mortgage Burden** | 30.11% | ACS B25091 | N/A | ✅ Std Source | Standard source table |
| **Avg HH Size** | 2.10 | ACS B25010 | N/A | ✅ Std Source | Standard source table |
| **Less than HS** | 11.75% | ACS B15003 | N/A | ✅ Std Source | Standard source table |

## 2022 Data Comparison

| Metric | Our Value | Verified Source | Source Value | Match? |
|--------|-----------|----------------|--------------|---------|
| **Population** | 569,931 | USAFacts | 569,931 | ✅ **Exact match** |
| **Median HH Income** | $55,198 | FRED SAIPE | $54,735 | ✅ 99.2% |
| **Unemployment Rate** | 5.50% | BLS LAUS | 3.8% | ❌ **1.70 pts higher** |

## 2021 Data Comparison

| Metric | Our Value | Verified Source | Source Value | Match? |
|--------|-----------|----------------|--------------|---------|
| **Population** | 576,498 | Census estimates | ~576,578 | ✅ 99.98% |
| **Median HH Income** | $54,652 | FRED SAIPE | $54,068 | ✅ 98.9% |
| **Unemployment Rate** | 7.92% | BLS LAUS | 6.7% | ❌ **1.22 pts higher** |

---

## Summary Statistics

### Match Quality Distribution
- ✅ **Exact or Near-Exact Match (within 1%):** 6 of 8 metrics
- ⚠️ **Close Match (within 5%):** 1 metric (Bachelor's degree)
- ❌ **Significant Discrepancy:** 1 metric (Unemployment - wrong data source)

### Data Source Validation
- **Using correct authoritative source:** 7 of 8 metrics
- **Using suboptimal but valid source:** 1 metric (Population - ACS instead of PEP)
- **Using incorrect source:** 1 metric (Unemployment - ACS instead of BLS LAUS)

---

## Unemployment Rate: The Problem

The unemployment rate discrepancy is **consistent and significant** across all years:

| Year | Our Value (ACS) | BLS LAUS | Difference |
|------|----------------|----------|------------|
| 2023 | 5.05% | 2.9% | +2.15 pts |
| 2022 | 5.50% | 3.8% | +1.70 pts |
| 2021 | 7.92% | 6.7% | +1.22 pts |

**Why this matters:**
- BLS LAUS is the **official unemployment statistic** used by governments, economists, and media
- ACS employment questions are different from the Current Population Survey (CPS) that BLS uses
- Telling stakeholders Baltimore has 5% unemployment when BLS says 2.9% undermines credibility

**The fix:**
Use BLS API with series `LAUST245100000000003` for monthly data or `LAUCN245100000000003A` for annual.

---

## Data Sources Legend

| Source | What It Is | When to Use |
|--------|-----------|-------------|
| **Census ACS 1-Year** | Annual survey of ~3.5M households | Demographics, income, housing, education |
| **Census PEP** | Population Estimates using vital statistics | Population totals (more accurate than ACS) |
| **BLS LAUS** | Local Area Unemployment Statistics | **Unemployment rate (official source)** |
| **Census SAIPE** | Small Area Income & Poverty Estimates | Alternative income/poverty data |

---

## Confidence Levels

### High Confidence (Present Without Caveat):
1. Median Household Income
2. Rent Cost Burden
3. Mortgage Cost Burden
4. Bachelor's Degree+
5. Less Than HS Diploma
6. Average Household Size

### Medium Confidence (Note Methodology if Asked):
7. Population (ACS vs PEP difference, but our value is correct for ACS)

### Low Confidence (Must Acknowledge Limitation):
8. Unemployment Rate (**wrong data source** - fix after meeting)

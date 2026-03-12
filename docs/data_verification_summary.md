# Data Verification Summary - Quick Reference

**For March 23 Meeting**

## ✅ Metrics Verified and Good to Present

| Metric | 2023 Value | Status | Source |
|--------|-----------|--------|---------|
| **Median Household Income** | $59,579 | ✅ Verified | ACS 1-Year B19013 |
| **Rent Cost Burden (30%+)** | 54.97% | ✅ Verified | ACS 1-Year B25070 |
| **Mortgage Cost Burden (30%+)** | 30.11% | ✅ Verified | ACS 1-Year B25091 |
| **Bachelor's Degree+** | 37.07% | ✅ Verified | ACS 1-Year B15003 |
| **Less Than HS Diploma** | 11.75% | ✅ Verified | ACS 1-Year B15003 |
| **Average Household Size** | 2.10 | ✅ Verified | ACS 1-Year B25010 |

## ⚠️ Metrics with Caveats

### Population: 565,239
- **Status:** ⚠️ Accurate, but not best source
- **Current source:** ACS 1-Year B01003 (survey-based)
- **Better source:** Census Population Estimates Program (PEP)
- **For meeting:** Present as-is, note it's from ACS if asked

### Unemployment Rate: 5.05%
- **Status:** ⚠️ Wrong data source (values are ~2% too high)
- **Current source:** ACS 1-Year B23025
- **Correct source:** BLS LAUS (shows 2.9% for 2023)
- **For meeting:** **Acknowledge this is ACS-based, not official BLS unemployment**

---

## Key Talking Points for March 23

### Strengths:
1. **Housing affordability data is solid** - Over half of renters (55%) are cost-burdened
2. **Income growth is strong** - Median household income up from $32,456 (2005) to $59,579 (2023) - 84% increase
3. **Education levels improving** - Bachelor's degree+ up from 24.74% (2008) to 37.07% (2023)
4. **All data from Census Bureau's ACS program** - nationally recognized standard

### Caveats to Mention:
1. **Unemployment rate is from ACS** (survey-based), not BLS official statistics
   - Our value: 5.05% | BLS official: 2.9%
   - We'll switch to BLS source after this meeting
2. **Population declining** - Baltimore lost ~72k people (11%) from 2010-2023
3. **All metrics use 1-Year ACS estimates** - more current but higher sampling error than 5-Year

---

## If Asked: "How accurate is this data?"

**Answer:**
"Six of eight metrics are verified against authoritative sources and match published data. For median income, housing costs, and education, our values align with what the Baltimore Banner, AFRO, and other outlets have reported using the same Census data.

Our unemployment figure comes from the Census survey (ACS) rather than the Bureau of Labor Statistics' official unemployment program (LAUS), so it's higher than what BLS reports. We're planning to switch to BLS data after this meeting for more precise unemployment tracking.

All data is from the U.S. Census Bureau's American Community Survey, which is the standard source for city-level demographic and economic indicators."

---

## Action Items After Meeting

### Immediate (this week):
1. ✅ Switch unemployment data to BLS LAUS API
2. ✅ Consider switching population to Census PEP
3. ✅ Add source methodology notes to Power BI dashboard

### Future Enhancements:
- Add margin of error (MOE) to visualizations
- Create data quality metadata fields
- Document methodology differences in dashboard
